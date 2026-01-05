from exams.models import Question
import copy
from django.utils import timezone

def grade_exam_logic(exam, already_scored):
    submission = exam.submission
    selected_answers_map = submission.selected_answers_map
    results_map = {}
    final_score = 0 #num of questions answered correctly
    question_map = copy.deepcopy(exam.question_map)
    question_map = {v:k for k,v in question_map.items()} #now question id to question number
    questions = Question.objects.filter(id__in=question_map.keys()).distinct().values('id','question_text','question_type','course','option_a','option_b','option_c','option_d','expected_answer')
    for question in questions:
        qnum = question_map[str(question['id'])] #qnum is question number
        selected = selected_answers_map[qnum] 
        if selected == question["expected_answer"]:
            final_score += 1

        results_map[qnum] = {
            'question':question,
            'selected_answer':selected_answers_map[qnum],
            'is_correct': selected == question["expected_answer"]

        }

    if already_scored == False:
        submission.final_score = final_score
        submission.already_scored = True
        submission.time_scored = timezone.now()
        submission.save()

    return results_map, submission.final_score
