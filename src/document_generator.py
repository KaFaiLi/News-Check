"""Module for generating Word documents with news summaries."""

import os
from datetime import datetime
from typing import List, Dict, Optional
import requests
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_PARAGRAPH_ALIGNMENT
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.config import OPENAI_API_KEY, OPENAI_API_BASE, AZURE_DEPLOYMENT_NAME, AZURE_API_VERSION, OUTPUT_DIR
from src.config import INCLUDE_DEGRADATION_WARNING
from src.models import ArticleAnalysis, TrendAnalysis, BriefSummary, DetailedReport, DegradationStatus
from urllib.parse import urljoin
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class DocumentGenerator:
    def __init__(self, output_dir=OUTPUT_DIR, llm_instance: Optional[AzureChatOpenAI] = None):
        self.output_dir = output_dir
        self.llm = llm_instance
        os.makedirs(self.output_dir, exist_ok=True)
        self.summary_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert news analyst. Synthesize the key themes and most significant developments from the provided list of recent news article titles and their insights."),
            ("user", "Please provide a concise overall summary (3-4 sentences) based on the following articles:\n\n{article_summaries}\n\nOverall Summary:")
        ])
        if self.llm:
            self.summary_chain = self.summary_prompt | self.llm
        else:
             self.summary_chain = None

    def _set_doc_margins(self, document):
        sections = document.sections
        for section in sections:
            section.top_margin = Inches(1)
            section.bottom_margin = Inches(1)
            section.left_margin = Inches(1)
            section.right_margin = Inches(1)

    def _add_styled_paragraph(self, document, text, size=11, bold=False, alignment=WD_PARAGRAPH_ALIGNMENT.LEFT):
        paragraph = document.add_paragraph()
        paragraph.alignment = alignment
        run = paragraph.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(size)
        run.bold = bold
        paragraph.paragraph_format.space_after = Pt(6)
        return paragraph

    def _generate_overall_summary(self, top_articles: List[Dict]) -> str:
        """Generates an overall summary using the LLM based on top articles."""
        if not self.llm or not self.summary_chain:
            print("LLM instance not available for generating overall summary.")
            return "Overall summary could not be generated (LLM not configured)."

        # Prepare the input for the LLM
        summary_input = []
        for item in top_articles:
            title = item.get('article', {}).get('title', 'No Title')
            insight = item.get('analysis', {}).get('insights', 'N/A')
            # Ensure insight is a string, handling None or potential non-string types
            insight_str = str(insight) if insight else 'N/A'
            summary_input.append(f"Title: {title}\nInsight: {insight_str}\n---")

        if not summary_input:
            return "No articles available to generate a summary."

        formatted_input = "\n".join(summary_input)

        try:
            print("Generating overall summary with LLM...")
            response = self.summary_chain.invoke({"article_summaries": formatted_input})
            print("Overall summary generated.")
            return str(response.content)
        except Exception as e:
            print(f"Error generating overall summary with LLM: {e}")
            return f"Overall summary could not be generated due to an error: {e}"

    def generate_brief_summary(self, top_articles: List[Dict], degradation_status: Optional[DegradationStatus] = None):
        """Generates a brief Word document summary (e.g., top 3 articles)."""
        document = Document()
        self._set_doc_margins(document)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"brief_news_summary_{timestamp}.docx"
        filepath = os.path.join(self.output_dir, filename)

        self._add_styled_paragraph(document, "Brief News Summary", size=16, bold=True, alignment=WD_PARAGRAPH_ALIGNMENT.CENTER)
        self._add_styled_paragraph(document, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", size=10, alignment=WD_PARAGRAPH_ALIGNMENT.CENTER)
        
        # Add degradation warning if applicable (Phase 5)
        if INCLUDE_DEGRADATION_WARNING and degradation_status and degradation_status.is_degraded:
            document.add_paragraph()
            self._add_styled_paragraph(document, "⚠️ DEGRADATION WARNING", size=12, bold=True)
            warning_text = (
                f"This report was generated under degraded conditions due to sustained blocking/errors.\n"
                f"Success Rate: {degradation_status.success_rate:.1%} | "
                f"Failed Attempts: {degradation_status.failed_attempts}/{degradation_status.total_attempts} | "
                f"Collected Results: {degradation_status.collected_results_count if degradation_status.collected_results_count > 0 else len(top_articles)} articles"
            )
            self._add_styled_paragraph(document, warning_text, size=10)
            if degradation_status.warnings:
                for warning in degradation_status.warnings[:3]:  # Show top 3 warnings
                    self._add_styled_paragraph(document, f"  • {warning}", size=9)
        
        document.add_paragraph()

        # Add overall summary at the top
        overall_summary_text = self._generate_overall_summary(top_articles)
        self._add_styled_paragraph(document, "Overall Summary", size=12, bold=True)
        self._add_styled_paragraph(document, overall_summary_text, size=11)
        document.add_paragraph()

        # Include only the top 3 articles for the brief summary
        for i, item in enumerate(top_articles[:3], 1):
            article = item.get('article', {})
            analysis = item.get('analysis', {})
            title = article.get('title', 'No Title Provided')
            source = article.get('source', 'Unknown Source')
            pub_time_str = article.get('published_time', 'Unknown Time')
            url = article.get('url', '#')
            
            try:
                pub_time = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M') if pub_time_str != 'Unknown Time' else pub_time_str
            except:
                pub_time = pub_time_str

            insights = analysis.get('insights', 'No analysis available.')
            insights_str = str(insights) if insights else 'No analysis available.'

            # Add content as styled paragraphs
            self._add_styled_paragraph(document, f"{i}. {title}", size=12, bold=True)
            self._add_styled_paragraph(document, f"   Source: {source} | Published: {pub_time}", size=10)
            self._add_styled_paragraph(document, f"   Analysis: {insights_str}", size=11)
            p = self._add_styled_paragraph(document, f"   Link: ", size=10)
            p.add_run(url).font.size = Pt(10)

            # Add spacing after each article
            document.add_paragraph()

        document.save(filepath)
        return filepath

    def generate_detailed_report(self, top_articles: List[Dict], degradation_status: Optional[DegradationStatus] = None):
        """Generates a detailed Word document report including a table of contents."""
        document = Document()
        self._set_doc_margins(document)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"detailed_news_report_{timestamp}.docx"
        filepath = os.path.join(self.output_dir, filename)

        # Add title
        self._add_styled_paragraph(document, "Detailed News Report", size=16, bold=True, alignment=WD_PARAGRAPH_ALIGNMENT.CENTER)
        self._add_styled_paragraph(document, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", size=10, alignment=WD_PARAGRAPH_ALIGNMENT.CENTER)
        
        # Add degradation warning if applicable (Phase 5)
        if INCLUDE_DEGRADATION_WARNING and degradation_status and degradation_status.is_degraded:
            document.add_paragraph()
            self._add_styled_paragraph(document, "⚠️ DEGRADATION WARNING", size=12, bold=True)
            warning_text = (
                f"This report was generated under degraded conditions due to sustained blocking/errors.\n"
                f"Success Rate: {degradation_status.success_rate:.1%} | "
                f"Failed Attempts: {degradation_status.failed_attempts}/{degradation_status.total_attempts} | "
                f"Collected Results: {degradation_status.collected_results_count if degradation_status.collected_results_count > 0 else len(top_articles)} articles"
            )
            self._add_styled_paragraph(document, warning_text, size=10)
            if degradation_status.warnings:
                for warning in degradation_status.warnings[:5]:  # Show top 5 warnings in detailed report
                    self._add_styled_paragraph(document, f"  • {warning}", size=9)
        
        document.add_paragraph()

        # Add Table of Contents
        self._add_styled_paragraph(document, "Table of Contents", size=14, bold=True)
        for i, item in enumerate(top_articles, 1):
            title = item.get('article', {}).get('title', 'No Title Provided')
            toc_paragraph = self._add_styled_paragraph(document, f"{i}. {title}", size=11)
            toc_paragraph.paragraph_format.left_indent = Inches(0.25)
        document.add_paragraph()  # Add spacing after TOC

        # Add the fixed introductory lines
        self._add_styled_paragraph(document, "The following are the top news items for review.", size=11)
        self._add_styled_paragraph(document, "For more detailed analysis of each article, please refer to the individual insights provided below or the source links.", size=11)
        document.add_paragraph()

        # Add detailed articles
        self._add_styled_paragraph(document, "Top News Details", size=14, bold=True)

        for i, item in enumerate(top_articles, 1):
            article = item.get('article', {})
            analysis = item.get('analysis', {})
            title = article.get('title', 'No Title Provided')
            source = article.get('source', 'Unknown Source')
            pub_time_str = article.get('published_time', 'Unknown Time')
            url = article.get('url', '#')

            try:
                pub_time = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M') if pub_time_str != 'Unknown Time' else pub_time_str
            except:
                pub_time = pub_time_str

            insights = analysis.get('insights', 'No analysis available.')
            insights_str = str(insights) if insights else 'No analysis available.'

            self._add_styled_paragraph(document, f"{i}. {title}", size=12, bold=True)
            self._add_styled_paragraph(document, f"   Source: {source} | Published: {pub_time}", size=10)
            self._add_styled_paragraph(document, f"   Analysis: {insights_str}", size=11)
            p = self._add_styled_paragraph(document, f"   Link: ", size=10)
            p.add_run(url).font.size = Pt(10)
            document.add_paragraph()

        document.save(filepath)
        return filepath

    def generate_email_content(self, top_articles: List[Dict], degradation_status: Optional[DegradationStatus] = None) -> str:
        """Generates HTML content ready for copying into Outlook email."""
        
        # Generate timestamp for the email header
        timestamp = datetime.now().strftime('%A, %B %d, %Y') # e.g., Monday, June 10, 2024
        
        # Start building HTML content with email-client-friendly styling
        # Using CSS classes and a <style> block for better organization and some responsiveness
        html_content = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI & Fintech News Digest</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            background-color: #f0f2f5; /* Light grey background for the email client viewport */
            font-family: Arial, sans-serif;
            -webkit-text-size-adjust: 100%; /* Prevent iOS font scaling */
            -ms-text-size-adjust: 100%; /* Prevent Windows Mobile font scaling */
        }}
        table {{ /* Outlook fix for unwanted spacing */
            border-collapse: collapse;
            mso-table-lspace: 0pt;
            mso-table-rspace: 0pt;
        }}
        .email-container {{
            max-width: 700px;
            margin: 20px auto; /* Centering and top/bottom margin */
            background-color: #ffffff; /* White background for the content area */
            border: 1px solid #dddddd;
            font-family: Arial, sans-serif;
            font-size: 11pt;
            color: #333333;
        }}
        .header {{
            padding: 25px 30px;
            border-bottom: 4px solid #E9041E; /* Company red accent */
            background-color: #ffffff;
        }}
        .header h1 {{
            font-size: 24pt;
            color: #1A1A1A; /* Darker, professional black */
            margin: 0 0 5px 0;
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            font-weight: bold;
        }}
        .header p {{
            font-size: 11pt;
            color: #555555;
            margin: 0;
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        }}
        .intro-section {{
            padding: 25px 30px;
            background-color: #f8f8f8; /* Very light grey for intro box */
        }}
        .intro-section p {{
            margin: 0;
            color: #333333;
            line-height: 1.6;
            font-size: 11pt;
        }}
        .stories-title-section {{
            padding: 25px 30px 15px 30px; /* Added more top padding */
        }}
        .stories-title-section h3 {{
            font-size: 17pt;
            color: #1A1A1A;
            margin: 0;
            padding-bottom: 8px;
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            font-weight: bold;
        }}
        .article-item {{
            padding: 0px 30px 25px 30px; /* Padding around each article block */
        }}
        .article-table {{
            width: 100%;
            border-collapse: collapse;
            border: 1px solid #e0e0e0; /* Softer border for article box */
        }}
        .article-accent-cell {{
            width: 6px; /* Width of the red accent bar */
            background-color: #E9041E;
            font-size: 1px; /* Fix for some clients adding height */
            line-height: 1px; /* Fix for some clients adding height */
        }}
        .article-content-cell {{
            padding: 20px;
        }}
        .article-title {{ /* Encapsulating paragraph for title */
            margin: 0 0 8px 0;
        }}
        .article-title a {{
            font-size: 14pt;
            color: #222222; /* Dark, near-black for article titles */
            font-weight: bold;
            text-decoration: none;
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        }}
        .article-title a:hover {{
            text-decoration: underline;
        }}
        .article-meta {{
            margin: 0 0 12px 0; /* Adjusted margin */
            font-size: 10pt;
            color: #555555;
            font-family: Arial, sans-serif;
        }}
        .article-insights {{
            font-size: 11pt;
            color: #333333;
            line-height: 1.6;
            font-family: Arial, sans-serif;
        }}
        .article-insights ul {{
            margin: 10px 0 0 0; /* Top margin for ul */
            padding-left: 20px; /* Indent for bullet points */
        }}
        .article-insights li {{
            margin-bottom: 6px; /* Spacing between list items */
        }}
        .article-insights p {{ /* Paragraphs within insights */
            margin: 10px 0 0 0;
        }}
        .read-more-link a {{
            font-size: 10.5pt;
            color: #444444; /* Dark grey for the link */
            text-decoration: none;
            font-weight: bold;
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        }}
        .read-more-link a:hover {{
            text-decoration: underline;
        }}
        .footer {{
            padding: 25px 30px;
            border-top: 1px solid #dddddd;
            background-color: #f0f0f0; /* Light grey for footer */
            text-align: center;
        }}
        .footer p {{
            margin: 0 0 8px 0; /* Increased bottom margin */
            font-size: 9.5pt; /* Slightly adjusted for readability */
            color: #666666;
            line-height: 1.5;
        }}
        .footer p:last-child {{
            margin-bottom: 0;
        }}
        /* Alternating background colors for articles */
        .bg-white {{ background-color: #ffffff; }}
        .bg-lightgrey {{ background-color: #f9f9f9; }}

        /* Responsive considerations */
        @media screen and (max-width: 600px) {{
            .email-container {{
                width: 100% !important;
                margin: 0 auto !important;
                border-left: none !important;
                border-right: none !important;
            }}
            .header, .intro-section, .stories-title-section, .article-item, .footer {{
                padding-left: 20px !important;
                padding-right: 20px !important;
            }}
            .header h1 {{ font-size: 20pt !important; }}
            .stories-title-section h3 {{ font-size: 15pt !important; }}
            .article-title a {{ font-size: 13pt !important; }}
        }}
    </style>
</head>
<body>
    <table class="email-container" width="700" align="center" cellpadding="0" cellspacing="0" role="presentation" style="width: 700px;">
        <!-- Header -->
        <tr>
            <td class="header">
                <h1>AI & Fintech News Digest</h1>
                <p>Daily Briefing &bull; {timestamp}</p>
                    </td>
                </tr>
                
        <!-- Intro Section -->
        <tr>
            <td class="intro-section">
                <p>
                    Welcome to your daily AI and Fintech news briefing. This digest highlights key developments
                    in artificial intelligence and financial technology from the past 24 hours.
                    Click on any article title to read the full story.
                </p>"""
        
        # Add degradation warning to email (Phase 5)
        if INCLUDE_DEGRADATION_WARNING and degradation_status and degradation_status.is_degraded:
            html_content += f"""
                <div style="margin-top: 15px; padding: 15px; background-color: #fff3cd; border-left: 4px solid #ffc107;">
                    <p style="margin: 0; color: #856404; font-weight: bold; font-size: 11pt;">
                        ⚠️ DEGRADATION WARNING
                    </p>
                    <p style="margin: 5px 0 0 0; color: #856404; font-size: 10pt;">
                        This report was generated under degraded conditions due to sustained blocking/errors.<br>
                        Success Rate: {degradation_status.success_rate:.1%} | 
                        Failed Attempts: {degradation_status.failed_attempts}/{degradation_status.total_attempts} | 
                        Collected Results: {degradation_status.collected_results_count if degradation_status.collected_results_count > 0 else len(top_articles)} articles
                    </p>
                </div>"""
        
        html_content += """
                        </p>
                    </td>
                </tr>

        <!-- Spacer row for visual separation -->
        <tr><td style="height:10px; background-color: #ffffff; font-size: 1px; line-height: 1px;">&nbsp;</td></tr>

        <!-- Top Stories Title -->
        <tr>
            <td class="stories-title-section">
                <h3>Today's Top Stories</h3>
                    </td>
                </tr>
        """
        
        # Add top 3 articles with new styling
        for i, item in enumerate(top_articles[:3], 1):
            article = item.get('article', {})
            analysis = item.get('analysis', {})
            
            title = article.get('title', 'No Title Provided')
            source = article.get('source', 'Unknown Source')
            pub_time_str = article.get('published_time', 'Unknown Time')
            url = article.get('url', '#')
            
            try:
                pub_time = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00')).strftime('%I:%M %p') if pub_time_str != 'Unknown Time' else pub_time_str
            except:
                pub_time = pub_time_str # Fallback to original string if parsing fails
            
            insights = analysis.get('insights', None) # Get None to better distinguish from "No analysis" string
            
            processed_insights_html = ""
            if isinstance(insights, list) and insights:
                # Filter out empty strings from list before joining
                valid_insights = [str(insight).strip() for insight in insights if str(insight).strip()]
                if valid_insights:
                    processed_insights_html = "<ul style='margin: 10px 0 0 0; padding-left: 20px;'>" + "".join(f"<li style='margin-bottom: 6px;'>{insight}</li>" for insight in valid_insights) + "</ul>"
                else:
                    processed_insights_html = "<p style='margin: 10px 0 0 0;'>No specific insights provided.</p>"
            elif isinstance(insights, str) and insights.strip():
                insights_str = insights.strip()
                if '•' in insights_str: # Check if string contains bullet points
                    points = [p.strip() for p in insights_str.split('•') if p.strip()]
                    if points:
                         processed_insights_html = "<ul style='margin: 10px 0 0 0; padding-left: 20px;'>" + "".join(f"<li style='margin-bottom: 6px;'>{point}</li>" for point in points) + "</ul>"
                    else: # String had '•' but resulted in no points
                        processed_insights_html = f"<p style='margin: 10px 0 0 0;'>{insights_str}</p>"
                else: # Plain string without bullets
                    processed_insights_html = f"<p style='margin: 10px 0 0 0;'>{insights_str}</p>"
            else: # Handles None, empty string, or empty list for insights
                 processed_insights_html = "<p style='margin: 10px 0 0 0;'>No analysis available for this article.</p>"

            # Alternating background for article content cell
            content_bg_class = 'bg-lightgrey' if i % 2 == 0 else 'bg-white'
            
            html_content += f"""\
        <!-- Article {i} -->
        <tr>
            <td class="article-item">
                <table class="article-table" cellpadding="0" cellspacing="0" role="presentation">
                    <tr>
                        <td class="article-accent-cell" style="width: 6px; background-color: #E9041E; font-size: 1px; line-height: 1px;">&nbsp;</td>
                        <td class="article-content-cell {content_bg_class}">
                            <p class="article-title">
                                <a href="{url}" target="_blank">{i}. {title}</a>
                            </p>
                            <p class="article-meta">
                                {source} &bull; {pub_time}
                            </p>
                            <div class="article-insights">
                                {processed_insights_html}
                            </div>
                            <p class="read-more-link" style="margin-top: 12px; margin-bottom: 0;">
                                <a href="{url}" target="_blank">Read Full Article &rarr;</a>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
            """
        
        # Add footer with new styling
        html_content += f"""\
        <!-- Spacer row before footer -->
        <tr><td style="height:10px; background-color: #ffffff; font-size: 1px; line-height: 1px;">&nbsp;</td></tr>
        
        <!-- Footer -->
        <tr>
            <td class="footer">
                <p>
                    This AI & Fintech News Digest is automatically generated. For a more comprehensive overview, the full report may be available as an attachment.
                </p>
                <p>
                    For feedback or inquiries, please reply to this email.
                </p>
                <p style="margin-top:15px; color: #888888;">&copy; {datetime.now().year} [Your Company Name]. All rights reserved.</p>
                                </td>
                            </tr>
    </table> <!-- End of email-container table -->
</body>
</html>
"""
        
        # Save the HTML content to a file for backup/review
        timestamp_file = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"email_content_{timestamp_file}.html"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        return html_content 