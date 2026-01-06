from rest_framework.pagination import PageNumberPagination
from utils.response_format import success_response
from django.core.paginator import InvalidPage
from rest_framework.exceptions import NotFound

class CustomPagination(PageNumberPagination):
    
    def get_paginated_response(self, data):
        return success_response(data={
            "response_data": data,
            'page_info': {
                'count': self.page.paginator.count,
                'next': self.get_next_link(),
                'previous': self.get_previous_link()
            },
        })


    def get_paginated_response_schema(self, schema):
        """This is telling how to draw the Swagger UI for this pagination class"""
        return {
            'type': 'object',
            'properties': {
                'data': {
                    'type': 'object',
                    'properties': {
                        'response_data': schema, 
                        'page_info': {
                            'type': 'object',
                            'properties': {
                                'count': {'type': 'integer', 'example': 123},
                                'next': {'type': 'string', 'nullable': True, 'format': 'uri'},
                                'previous': {'type': 'string', 'nullable': True, 'format': 'uri'},
                            }
                        }
                    }
                }
            },
        }
    def paginate_queryset(self, queryset, request, view=None ):
        """
        Paginate a queryset if required, either returning a
        page object, or `None` if pagination is not configured for this view.
        """

        page_size=request.query_params.get('page_size')
        page_size = 5 if page_size == None or page_size.isdigit() == False else page_size
        paginator = self.django_paginator_class(queryset, page_size)
        page_number = self.get_page_number(request, paginator)

        try:
            self.page = paginator.page(page_number)
        except InvalidPage as exc:
            msg = self.invalid_page_message.format(
                page_number=page_number, message=str(exc)
            )
            raise NotFound(msg)

        if paginator.num_pages > 1 and self.template is not None:
            self.display_page_controls = True

        self.request = request
        return list(self.page)


