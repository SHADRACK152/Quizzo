#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, generate_exam_advice

def test_ai_advice():
    with app.app_context():
        # Test wrong questions data
        wrong_questions = [
            {
                'question': 'What is the primary purpose of indexing in a database?',
                'student_answer': 'A',
                'correct_answer': 'C',
                'question_type': 'multiple_choice'
            },
            {
                'question': 'What is the purpose of a database backup?',
                'student_answer': 'A', 
                'correct_answer': 'C',
                'question_type': 'multiple_choice'
            }
        ]
        
        # Test the AI advice generation
        advice = generate_exam_advice("Advanced database management", wrong_questions, 50.0)
        
        print("AI Advice Generated:")
        print("===================")
        print(f"Overall Advice: {advice.get('overall_advice', 'None')}")
        print(f"Study Tips: {advice.get('study_tips', [])}")
        print(f"Question Advice: {advice.get('question_advice', {})}")

if __name__ == '__main__':
    test_ai_advice()