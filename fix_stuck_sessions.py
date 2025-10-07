#!/usr/bin/env python3
"""
Fix stuck challenge sessions and complete them properly.
"""

from app import app, db, ChallengeSession, ChallengeAnswer, ChallengeQuestion, Challenge
from datetime import datetime, timezone
import json

def fix_stuck_sessions():
    """Fix challenge sessions that are stuck in progress"""
    
    with app.app_context():
        print("🔧 Checking for stuck challenge sessions...")
        
        # Find sessions that should be completed
        stuck_sessions = ChallengeSession.query.filter_by(status='in_progress').all()
        
        for session in stuck_sessions:
            print(f"\n📝 Checking session {session.id}...")
            
            # Get total questions for this challenge
            total_questions = ChallengeQuestion.query.filter_by(challenge_id=session.challenge_id).count()
            
            # Get answered questions
            answered_questions = ChallengeAnswer.query.filter_by(session_id=session.id).count()
            
            print(f"   Questions: {answered_questions}/{total_questions}")
            
            # If all questions are answered, complete the session
            if answered_questions >= total_questions and total_questions > 0:
                print(f"   ✅ Completing session {session.id}...")
                
                # Calculate score
                correct_answers = ChallengeAnswer.query.filter_by(
                    session_id=session.id, 
                    is_correct=True
                ).count()
                
                # Set completion details
                session.score = correct_answers
                session.percentage = round((correct_answers / total_questions) * 100)
                session.status = 'completed'
                session.end_time = datetime.now(timezone.utc)
                
                # Get challenge for point calculation
                challenge = Challenge.query.get(session.challenge_id)
                
                # Calculate points (import the function)
                from app import calculate_challenge_points
                try:
                    points_breakdown = calculate_challenge_points(session, challenge, total_questions)
                    session.points = points_breakdown['total']
                    session.points_breakdown = json.dumps(points_breakdown)
                    
                    print(f"   💎 Points earned: {session.points}")
                    print(f"   📊 Score: {correct_answers}/{total_questions} ({session.percentage}%)")
                    
                except Exception as e:
                    print(f"   ⚠️  Error calculating points: {e}")
                    # Set basic points without breakdown
                    session.points = 50 + (correct_answers * 10)  # Base + correctness
                
                db.session.commit()
                print(f"   ✅ Session {session.id} completed successfully!")
            
            else:
                print(f"   ⏳ Session {session.id} still in progress ({answered_questions}/{total_questions} answered)")
        
        print(f"\n🎉 Fixed {len([s for s in stuck_sessions if ChallengeSession.query.get(s.id).status == 'completed'])} stuck sessions!")

if __name__ == "__main__":
    fix_stuck_sessions()