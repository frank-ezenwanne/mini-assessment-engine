from exams.models import Question, Exam
import copy

def grade_exam_logic(exam, already_scored):
    submission = exam.submission
    selected_answers_map = submission.selected_answers_map
    results_map = {}
    final_score = 0 #num of questions answered correctly
    questions = Question.objects.filter(id__in=exam.question_map.keys()).distinct().values('question_text','question_type','course','option_a','option_b','option_c','option_d','expected_answer').first()
    question_map = copy.deepcopy(Exam.question_map)
    question_map = {v:k for k,v in question_map.items()} #now question id to question number
    for question in questions:
        qnum = question_map[question.id] #qnum is question number
        selection_question_map = {}
        if selected_answers_map[qnum] == question.expected_answer:
            final_score += 1
        selection_question_map['question'] = question
        selection_question_map['selected_answer'] = selected_answers_map[qnum]
        results_map[qnum] = selection_question_map

    if already_scored == False:
        submission.final_score = final_score
        submission.graded = True
        submission.save()

    return results_map, final_score
