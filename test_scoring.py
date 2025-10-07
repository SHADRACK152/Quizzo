#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, ExamSession, calculate_exam_score

def test_scoring():
    with app.app_context():
        # Test the scoring function
        exam_session = db.session.get(ExamSession, 1)
        if exam_session:
            correct, total, percentage = calculate_exam_score(exam_session)
            print(f'Scoring results:')
            print(f'Correct answers: {correct}')
            print(f'Total questions: {total}') 
            print(f'Score percentage: {percentage}%')
            
            # Expected: 3 correct out of 5 (60%)
            # Test answers: C, B, A, C, A
            # Correct answers: C, C, A, C, D
            # So questions 1, 3, 4 should be correct = 3/5 = 60%
            
            if correct == 3 and total == 5 and abs(percentage - 60.0) < 0.1:
                print('✅ Scoring is working correctly!')
            else:
                print('❌ Scoring issue detected')
                print(f'Expected: 3 correct out of 5 (60%), Got: {correct} out of {total} ({percentage}%)')
        else:
            print('No exam session found')

if __name__ == '__main__':
    test_scoring()