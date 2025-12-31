from drf_standardized_errors.formatter import ExceptionFormatter
from drf_standardized_errors.types import ErrorResponse


class CustomExceptionFormatter(ExceptionFormatter):

        def format_error_response(self, error_response: ErrorResponse):
            errors=[]
            for error in error_response.errors:
                errors.append({
                    'type': error_response.type,
                    'code': error.code,
                    'error':error.detail,
                    'field_name':error.attr,
                })
            return errors