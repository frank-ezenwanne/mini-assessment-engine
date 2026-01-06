from .models import Exam, Question
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.cache import cache
from django.utils import timezone

@receiver([post_save,post_delete], sender = Question)
def clear_cache_questchange(sender, instance, created=False, **kwargs):
    cache.clear() #clear all caches especially exam question map


@receiver(pre_save, sender = Exam)
def pre_clear_cache_examquest(sender, instance, **kwargs):
    if instance._state.adding == False:
        old = Exam.objects.get(pk=instance.pk)
        instance._question_map = old.question_map #hold on to previous question map instance before post_save
        instance._ended = old.ended

@receiver(post_save, sender = Exam)
def clear_cache_exam_questchange(sender, instance, created, **kwargs):
    if not created:
        if instance._question_map:
            if instance._question_map != instance.question_map: #clear cache for any change in question map
                cache.delete(f'exam_cache_{instance.id}')

        if instance._ended == False and instance.ended == True:
            instance.time_ended = timezone.now()
            instance.save()
            cache.delete(f'exam_cache_{instance.id}')
        
    instance.full_clean()