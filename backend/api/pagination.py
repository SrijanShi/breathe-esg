from rest_framework.pagination import CursorPagination, PageNumberPagination


class StandardCursorPagination(CursorPagination):
    page_size = 50
    ordering = "-created_at"
    page_size_query_param = "page_size"
    max_page_size = 200


class EmissionCursorPagination(CursorPagination):
    page_size = 50
    ordering = "-activity_date"
    page_size_query_param = "page_size"
    max_page_size = 200


class AuditLogCursorPagination(CursorPagination):
    page_size = 50
    ordering = "-timestamp"
    page_size_query_param = "page_size"
    max_page_size = 200


class SmallPagePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
