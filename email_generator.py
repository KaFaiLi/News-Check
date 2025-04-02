from typing import Dict, List
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class EmailGenerator:
    def __init__(self):
        self.env = Environment(loader=FileSystemLoader('templates'))
        
        # Create templates directory if it doesn't exist
        os.makedirs('templates', exist_ok=True)
        
        # Create email template if it doesn't exist
        self._create_email_template()

    def _create_email_template(self):
        """Create the HTML email template if it doesn't exist"""
        template_path = 'templates/newsletter_template.html'
        if not os.path.exists(template_path):
            template_content = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }
        .header { background-color: #003366; color: white; padding: 20px; text-align: center; }
        .executive-summary { background-color: #f5f5f5; padding: 20px; margin: 20px 0; }
        .article { border-bottom: 1px solid #ddd; padding: 15px 0; }
        .article-title { color: #003366; font-size: 18px; margin-bottom: 10px; }
        .article-meta { color: #666; font-size: 14px; margin-bottom: 10px; }
        .article-summary { margin-bottom: 15px; }
        .why-matters { background-color: #f9f9f9; padding: 10px; border-left: 3px solid #003366; }
        .footer { text-align: center; margin-top: 30px; padding: 20px; background-color: #f5f5f5; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Quarterly AI Development Update</h1>
        <h2>Top 10 Insights - {{ quarter }} {{ year }}</h2>
    </div>

    <div class="executive-summary">
        <h3>Key Findings</h3>
        <ul>
        {% for point in executive_summary %}
            <li>{{ point }}</li>
        {% endfor %}
        </ul>
    </div>

    <h3>Top 10 AI Developments for Banking Auditors</h3>
    {% for article in articles %}
    <div class="article">
        <div class="article-title">
            <a href="{{ article.url }}">{{ article.title }}</a>
        </div>
        <div class="article-meta">
            Source: {{ article.source }} | Published: {{ article.published_time }}
        </div>
        <div class="article-summary">
            <ul>
            {% for point in article.analysis.key_points %}
                <li>{{ point }}</li>
            {% endfor %}
            </ul>
        </div>
        <div class="why-matters">
            <strong>Why It Matters to Banking Auditors:</strong><br>
            {{ article.analysis.banking_relevance }}
        </div>
    </div>
    {% endfor %}

    <div class="footer">
        <p>For questions or feedback, please contact:<br>
        {{ contact_email }}</p>
    </div>
</body>
</html>
'''
            with open(template_path, 'w') as f:
                f.write(template_content)

    def _get_quarter_info(self) -> tuple:
        """Get current quarter and year information"""
        now = datetime.now()
        quarter = (now.month - 1) // 3 + 1
        return f'Q{quarter}', str(now.year)

    def generate_newsletter(self, summary_data: Dict) -> str:
        """Generate newsletter HTML content"""
        template = self.env.get_template('newsletter_template.html')
        quarter, year = self._get_quarter_info()
        
        return template.render(
            quarter=quarter,
            year=year,
            executive_summary=summary_data['executive_summary'],
            articles=summary_data['top_articles'],
            contact_email=os.getenv('CONTACT_EMAIL', 'ai.updates@company.com')
        )