from exams.models import Question
import copy

def prepare_question_cache(exam):
    question_map = copy.deepcopy(exam.question_map)
    question_map_rev = {v:k for k,v in question_map.items()} #reversed..now question id to question num map...so we can easily flip back to qnum
    questions = Question.objects.filter(id__in=question_map_rev.keys()).distinct()

    question_map_cache = {question_map_rev[str(question.id)]: question for question in questions}

    return question_map_cache
