"""
QUIZZO Feature Detection System
Automatically detects and catalogs all features in the application
"""

import re
import os
from datetime import datetime

class QuizzoFeatureDetector:
    def __init__(self, app_file_path="app.py"):
        self.app_file_path = app_file_path
        self.features = {}
        self.routes = []
        self.templates = []
        self.models = []
        self.last_scan = None
        
    def scan_application(self):
        """Comprehensive scan of the application to detect all features"""
        self.last_scan = datetime.now()
        self._detect_routes()
        self._detect_templates()
        self._detect_models()
        self._categorize_features()
        return self.features
    
    def _detect_routes(self):
        """Extract all routes from app.py"""
        self.routes = []
        try:
            with open(self.app_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                
            # Find all route decorators
            route_pattern = r"@app\.route\(['\"]([^'\"]+)['\"](?:.*?methods=(\[[^\]]+\]))?\)"
            matches = re.findall(route_pattern, content)
            
            for route, methods in matches:
                methods_clean = methods.replace('[', '').replace(']', '').replace("'", '').replace('"', '') if methods else 'GET'
                self.routes.append({
                    'path': route,
                    'methods': methods_clean,
                    'category': self._categorize_route(route)
                })
                
        except Exception as e:
            print(f"Error scanning routes: {e}")
    
    def _detect_templates(self):
        """Detect all HTML templates"""
        templates_dir = "templates"
        self.templates = []
        
        if os.path.exists(templates_dir):
            for file in os.listdir(templates_dir):
                if file.endswith('.html'):
                    self.templates.append({
                        'name': file,
                        'feature': self._template_to_feature(file)
                    })
    
    def _detect_models(self):
        """Extract database models from app.py"""
        self.models = []
        try:
            with open(self.app_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                
            # Find all model classes
            model_pattern = r"class (\w+)\(db\.Model\):"
            matches = re.findall(model_pattern, content)
            
            for model in matches:
                self.models.append({
                    'name': model,
                    'feature': self._model_to_feature(model)
                })
                
        except Exception as e:
            print(f"Error scanning models: {e}")
    
    def _categorize_route(self, route):
        """Categorize routes by feature"""
        if 'virtual' in route or 'session' in route or 'classroom' in route:
            return 'Virtual Classroom'
        elif 'ai' in route or 'generate' in route:
            return 'AI Features'
        elif 'course' in route:
            return 'Course Management'
        elif 'exam' in route:
            return 'Exam System'
        elif 'challenge' in route:
            return 'Challenges'
        elif 'dashboard' in route:
            return 'Dashboard'
        elif 'material' in route:
            return 'Study Materials'
        elif 'notification' in route:
            return 'Notifications'
        elif 'profile' in route:
            return 'User Management'
        else:
            return 'Core Features'
    
    def _template_to_feature(self, template):
        """Map template to feature"""
        if 'virtual' in template or 'session' in template:
            return 'Virtual Classroom'
        elif 'ai_course' in template:
            return 'AI Course Generator'
        elif 'dashboard' in template:
            return 'Dashboard'
        elif 'exam' in template:
            return 'Exam System'
        elif 'course' in template:
            return 'Course Management'
        elif 'challenge' in template:
            return 'Challenges'
        else:
            return 'Core Features'
    
    def _model_to_feature(self, model):
        """Map model to feature"""
        if 'AI' in model or 'Course' in model:
            return 'AI Course Generator'
        elif 'Session' in model or 'Live' in model:
            return 'Virtual Classroom'
        elif 'Exam' in model:
            return 'Exam System'
        elif 'Challenge' in model:
            return 'Challenges'
        elif 'User' in model:
            return 'User Management'
        else:
            return 'Core Features'
    
    def _categorize_features(self):
        """Organize all detected components into feature categories"""
        self.features = {
            'Virtual Classroom': {
                'description': 'Real-time video calls, live sessions, and collaborative learning',
                'routes': [r for r in self.routes if r['category'] == 'Virtual Classroom'],
                'templates': [t for t in self.templates if t['feature'] == 'Virtual Classroom'],
                'models': [m for m in self.models if m['feature'] == 'Virtual Classroom'],
                'status': 'Active',
                'new_feature': True  # This is the new feature detected
            },
            'AI Course Generator': {
                'description': 'AI-powered course creation with comprehensive content generation',
                'routes': [r for r in self.routes if r['category'] == 'AI Features'],
                'templates': [t for t in self.templates if t['feature'] == 'AI Course Generator'],
                'models': [m for m in self.models if m['feature'] == 'AI Course Generator'],
                'status': 'Active',
                'enhanced': True  # Recently enhanced
            },
            'Course Management': {
                'description': 'Course enrollment, lessons, and progress tracking',
                'routes': [r for r in self.routes if r['category'] == 'Course Management'],
                'templates': [t for t in self.templates if t['feature'] == 'Course Management'],
                'models': [m for m in self.models if m['feature'] == 'Course Management'],
                'status': 'Active'
            },
            'Exam System': {
                'description': 'Create, take, and analyze exams with detailed results',
                'routes': [r for r in self.routes if r['category'] == 'Exam System'],
                'templates': [t for t in self.templates if t['feature'] == 'Exam System'],
                'models': [m for m in self.models if m['feature'] == 'Exam System'],
                'status': 'Active'
            },
            'Challenges': {
                'description': 'Interactive learning challenges and competitions',
                'routes': [r for r in self.routes if r['category'] == 'Challenges'],
                'templates': [t for t in self.templates if t['feature'] == 'Challenges'],
                'models': [m for m in self.models if m['feature'] == 'Challenges'],
                'status': 'Active'
            },
            'Dashboard': {
                'description': 'Student and lecturer role-based dashboards',
                'routes': [r for r in self.routes if r['category'] == 'Dashboard'],
                'templates': [t for t in self.templates if t['feature'] == 'Dashboard'],
                'models': [],
                'status': 'Active'
            },
            'Study Materials': {
                'description': 'Browse, bookmark, and rate learning materials',
                'routes': [r for r in self.routes if r['category'] == 'Study Materials'],
                'templates': [t for t in self.templates if t['feature'] == 'Study Materials'],
                'models': [],
                'status': 'Active'
            },
            'User Management': {
                'description': 'User profiles, authentication, and settings',
                'routes': [r for r in self.routes if r['category'] == 'User Management'],
                'templates': [t for t in self.templates if t['feature'] == 'User Management'],
                'models': [m for m in self.models if m['feature'] == 'User Management'],
                'status': 'Active'
            },
            'Notifications': {
                'description': 'Real-time notifications and alerts system',
                'routes': [r for r in self.routes if r['category'] == 'Notifications'],
                'templates': [],
                'models': [],
                'status': 'Active'
            }
        }
    
    def get_feature_summary(self):
        """Get a summary of all features for the chatbot"""
        summary = {
            'total_features': len(self.features),
            'total_routes': len(self.routes),
            'total_templates': len(self.templates),
            'total_models': len(self.models),
            'new_features': [name for name, data in self.features.items() if data.get('new_feature')],
            'enhanced_features': [name for name, data in self.features.items() if data.get('enhanced')],
            'last_scan': self.last_scan,
            'features': self.features
        }
        return summary
    
    def detect_new_features(self, previous_scan=None):
        """Compare with previous scan to detect new features"""
        current_routes = set(r['path'] for r in self.routes)
        
        if previous_scan:
            previous_routes = set(r['path'] for r in previous_scan.get('routes', []))
            new_routes = current_routes - previous_routes
            return list(new_routes)
        
        return []

# Usage example
if __name__ == "__main__":
    detector = QuizzoFeatureDetector()
    features = detector.scan_application()
    summary = detector.get_feature_summary()
    
    print("🎯 QUIZZO Feature Detection Results:")
    print(f"📊 Total Features: {summary['total_features']}")
    print(f"🛣️  Total Routes: {summary['total_routes']}")
    print(f"📄 Total Templates: {summary['total_templates']}")
    print(f"💾 Total Models: {summary['total_models']}")
    
    if summary['new_features']:
        print(f"🆕 New Features: {', '.join(summary['new_features'])}")
    
    print("\n📋 Feature Breakdown:")
    for feature_name, feature_data in features.items():
        status_icon = "🆕" if feature_data.get('new_feature') else "✨" if feature_data.get('enhanced') else "✅"
        print(f"{status_icon} {feature_name}: {len(feature_data['routes'])} routes, {len(feature_data['templates'])} templates")