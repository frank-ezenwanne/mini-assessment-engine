from rest_framework.exceptions import PermissionDenied, ValidationError
from django.core.exceptions import ObjectDoesNotExist
from exams.models import Exam

def check_exam_permission(exam, user):
    if exam.initiated_by != user:
        raise PermissionDenied('User not allowed !')
    
def get_exam_with_perm(exam, user):
    if exam:
        try:
            exam = Exam.objects.select_related('submission').get(id=exam)
        except ObjectDoesNotExist:
            raise ValidationError('Exam not found')
    check_exam_permission(exam, user)
    return exam