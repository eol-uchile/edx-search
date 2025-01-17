""" search business logic implementations """
from __future__ import absolute_import
from datetime import datetime
from django.conf import settings

from .filter_generator import SearchFilterGenerator
from .search_engine_base import SearchEngine
from .result_processor import SearchResultProcessor
from .utils import DateRange
import logging
log = logging.getLogger(__name__)  # pylint: disable=invalid-name
# Default filters that we support, override using COURSE_DISCOVERY_FILTERS setting if desired
DEFAULT_FILTER_FIELDS = ["org", "modes", "language"]


def course_discovery_filter_fields():
    """ look up the desired list of course discovery filter fields """
    return getattr(settings, "COURSE_DISCOVERY_FILTERS", DEFAULT_FILTER_FIELDS)


def course_discovery_facets():
    """ Discovery facets to include, by default we specify each filter field with unspecified size attribute """
    return getattr(settings, "COURSE_DISCOVERY_FACETS", {field: {} for field in course_discovery_filter_fields()})


class NoSearchEngineError(Exception):
    """ NoSearchEngineError exception to be thrown if no search engine is specified """


class QueryParseError(Exception):
    """QueryParseError will be thrown if the query is malformed.

    If a query has mismatched quotes (e.g. '"some phrase', return a
    more specific exception so the view can provide a more helpful
    error message to the user.

    """


def perform_search(
        search_term,
        user=None,
        size=10,
        from_=0,
        course_id=None):
    """ Call the search engine with the appropriate parameters """
    # field_, filter_ and exclude_dictionary(s) can be overridden by calling application
    # field_dictionary includes course if course_id provided
    (field_dictionary, filter_dictionary, exclude_dictionary) = SearchFilterGenerator.generate_field_filters(
        user=user,
        course_id=course_id
    )

    searcher = SearchEngine.get_search_engine(getattr(settings, "COURSEWARE_INDEX_NAME", "courseware_index"))
    if not searcher:
        raise NoSearchEngineError("No search engine specified in settings.SEARCH_ENGINE")

    results = searcher.search_string(
        search_term,
        field_dictionary=field_dictionary,
        filter_dictionary=filter_dictionary,
        exclude_dictionary=exclude_dictionary,
        size=size,
        from_=from_,
        doc_type="courseware_content",
    )

    # post-process the result
    for result in results["results"]:
        result["data"] = SearchResultProcessor.process_result(result["data"], search_term, user)

    results["access_denied_count"] = len([r for r in results["results"] if r["data"] is None])
    results["results"] = [r for r in results["results"] if r["data"] is not None]

    return results


def course_discovery_search(search_term=None, size=20, from_=0, field_dictionary=None, order_by="", year="", state="", classification=""):
    """
    Course Discovery activities against the search engine index of course details
    """
    # We'll ignore the course-enrollemnt informaiton in field and filter
    # dictionary, and use our own logic upon enrollment dates for these
    use_search_fields = ["org"]
    (search_fields, _, exclude_dictionary) = SearchFilterGenerator.generate_field_filters()
    use_field_dictionary = {}
    use_field_dictionary.update({field: search_fields[field] for field in search_fields if field in use_search_fields})
    if field_dictionary:
        use_field_dictionary.update(field_dictionary)
    #if not getattr(settings, "SEARCH_SKIP_ENROLLMENT_START_DATE_FILTERING", False):
    #    use_field_dictionary["enrollment_start"] = DateRange(None, datetime.utcnow())

    searcher = SearchEngine.get_search_engine(getattr(settings, "COURSEWARE_INDEX_NAME", "courseware_index"))
    if not searcher:
        raise NoSearchEngineError("No search engine specified in settings.SEARCH_ENGINE")
    filter_dictionary = {} #"hidden": False
    sort = ""
    if order_by == "newer":
        sort = "start:desc"
    if order_by == "older":
        sort = "start"
    if year != "" and year.isnumeric():
        year = int(year)
        use_field_dictionary["start"] = DateRange(datetime(year, 1, 1), datetime(year+1, 1, 1))
    if state in ['active', 'finished']:
        if state == 'active':
            use_field_dictionary["end"] = DateRange(datetime.utcnow(), None)
        else:
            use_field_dictionary["end"] = DateRange(None, datetime.utcnow())
    from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
    ids = list(CourseOverview.objects.exclude(catalog_visibility="both").values("id"))
    ids = [str(x['id']) for x in ids]
    exclude_dictionary["_id"] = ids
    if classification != "":
        try:
            from course_classification.helpers import get_courses_by_classification
            courses = get_courses_by_classification(int(classification))

            ids = list(CourseOverview.objects.exclude(id__in=courses).values("id"))
            ids = [str(x['id']) for x in ids]

            exclude_dictionary["_id"] += ids
        except Exception as e:
            log.error("Course Discovery - Error in course_classification get_courses_by_classification function, error: {}".format(str(e)))
            pass
    results = searcher.search(
        query_string=search_term,
        doc_type="course_info",
        size=size,
        from_=from_,
        field_dictionary=use_field_dictionary,
        filter_dictionary=filter_dictionary,
        exclude_dictionary=exclude_dictionary,
        facet_terms=course_discovery_facets(),
        sort=sort
    )
    try:
        from course_classification.helpers import set_data_courses
        results['results'] = set_data_courses(results['results'])
    except Exception as e:
        log.error("Course Discovery - Error in course_classification set_data_courses function, error: {}".format(str(e)))
        pass
    return results
