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
        """Generates HTML content ready for copying into Outlook email with inline styles."""
        
        # Generate timestamp for the email header
        timestamp = datetime.now().strftime('%A, %B %d, %Y') # e.g., Monday, June 10, 2024
        
        # Define color palette for consistency
        COLORS = {
            'background_grey': '#f3f4f6',
            'card_white': '#ffffff',
            'primary_red': '#dc2626',
            'heading_black': '#111827',
            'body_grey': '#374151',
            'border_grey': '#e5e7eb',
            'meta_grey': '#6b7280',
            'footer_grey': '#f9fafb',
            'footer_text': '#6b7280'
        }
        
        # Start building HTML content with inline styles for Outlook compatibility
        html_content = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI & Fintech News Digest</title>
</head>
<body style="margin: 0; padding: 0; background-color: {COLORS['background_grey']}; font-family: -apple-system, 'Segoe UI', Arial, sans-serif;">
    <!-- Outer wrapper table for background -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 0; padding: 0; background-color: {COLORS['background_grey']}; border-collapse: collapse; mso-table-lspace: 0pt; mso-table-rspace: 0pt;">
        <tr>
            <td align="center" style="padding: 20px 0;">
                <!-- Main container table (600px centered) -->
                <table width="600" cellpadding="0" cellspacing="0" border="0" style="width: 600px; max-width: 600px; background-color: {COLORS['card_white']}; border-collapse: collapse; mso-table-lspace: 0pt; mso-table-rspace: 0pt;">
                    <!-- Header with red bottom border -->
                    <tr>
                        <td style="padding: 24px 24px 20px 24px; border-bottom: 4px solid {COLORS['primary_red']}; background-color: {COLORS['card_white']};">
                            <h1 style="margin: 0 0 8px 0; padding: 0; font-size: 26px; font-weight: bold; color: {COLORS['heading_black']}; font-family: -apple-system, 'Segoe UI', Arial, sans-serif; line-height: 1.3;">AI & Fintech News Digest</h1>
                            <p style="margin: 0; padding: 0; font-size: 14px; color: {COLORS['meta_grey']}; font-family: -apple-system, 'Segoe UI', Arial, sans-serif; line-height: 1.4;">Daily Briefing &bull; {timestamp}</p>
                        </td>
                    </tr>
                    
                    <!-- Intro Section with grey background -->
                    <tr>
                        <td style="padding: 24px; background-color: {COLORS['background_grey']};">
                            <p style="margin: 0; padding: 0; font-size: 15px; color: {COLORS['body_grey']}; font-family: -apple-system, 'Segoe UI', Arial, sans-serif; line-height: 1.6;">
                                Welcome to your daily AI and Fintech news briefing. This digest highlights key developments
                                in artificial intelligence and financial technology from the past 24 hours.
                                Click on any article title to read the full story.
                            </p>"""
        
        # Add degradation warning to email (Phase 5)
        if INCLUDE_DEGRADATION_WARNING and degradation_status and degradation_status.is_degraded:
            html_content += f"""
                            <!-- Degradation Warning -->
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top: 16px; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 16px; background-color: #fef3c7; border-left: 4px solid #f59e0b;">
                                        <p style="margin: 0 0 8px 0; padding: 0; font-size: 15px; font-weight: bold; color: #92400e; font-family: -apple-system, 'Segoe UI', Arial, sans-serif;">
                                            ⚠️ DEGRADATION WARNING
                                        </p>
                                        <p style="margin: 0; padding: 0; font-size: 14px; color: #92400e; font-family: -apple-system, 'Segoe UI', Arial, sans-serif; line-height: 1.4;">
                                            This report was generated under degraded conditions due to sustained blocking/errors.<br>
                                            Success Rate: {degradation_status.success_rate:.1%} | 
                                            Failed Attempts: {degradation_status.failed_attempts}/{degradation_status.total_attempts} | 
                                            Collected Results: {degradation_status.collected_results_count if degradation_status.collected_results_count > 0 else len(top_articles)} articles
                                        </p>
                                    </td>
                                </tr>
                            </table>"""
        
        html_content += """
                        </td>
                    </tr>

                    <!-- Spacer row -->
                    <tr>
                        <td style="height: 16px; font-size: 1px; line-height: 1px;">&nbsp;</td>
                    </tr>

                    <!-- Top Stories Title -->
                    <tr>
                        <td style="padding: 0 24px 16px 24px;">
                            <h2 style="margin: 0; padding: 0; font-size: 20px; font-weight: bold; color: """ + COLORS['heading_black'] + """; font-family: -apple-system, 'Segoe UI', Arial, sans-serif; line-height: 1.3;">Today's Top Stories</h2>
                        </td>
                    </tr>
        """
        
        # Add top 3 articles with inline styling
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
            
            insights = analysis.get('insights', None)
            
            # Process insights into HTML with inline styles
            processed_insights_html = ""
            if isinstance(insights, list) and insights:
                # Filter out empty strings from list before joining
                valid_insights = [str(insight).strip() for insight in insights if str(insight).strip()]
                if valid_insights:
                    processed_insights_html = "<ul style='margin: 12px 0 0 0; padding-left: 20px; font-size: 15px; color: " + COLORS['body_grey'] + "; font-family: -apple-system, \"Segoe UI\", Arial, sans-serif; line-height: 1.6;'>"
                    for insight in valid_insights:
                        processed_insights_html += f"<li style='margin-bottom: 8px;'>{insight}</li>"
                    processed_insights_html += "</ul>"
                else:
                    processed_insights_html = "<p style='margin: 12px 0 0 0; padding: 0; font-size: 15px; color: " + COLORS['body_grey'] + "; font-family: -apple-system, \"Segoe UI\", Arial, sans-serif; line-height: 1.6;'>No specific insights provided.</p>"
            elif isinstance(insights, str) and insights.strip():
                insights_str = insights.strip()
                if '•' in insights_str: # Check if string contains bullet points
                    points = [p.strip() for p in insights_str.split('•') if p.strip()]
                    if points:
                        processed_insights_html = "<ul style='margin: 12px 0 0 0; padding-left: 20px; font-size: 15px; color: " + COLORS['body_grey'] + "; font-family: -apple-system, \"Segoe UI\", Arial, sans-serif; line-height: 1.6;'>"
                        for point in points:
                            processed_insights_html += f"<li style='margin-bottom: 8px;'>{point}</li>"
                        processed_insights_html += "</ul>"
                    else:
                        processed_insights_html = f"<p style='margin: 12px 0 0 0; padding: 0; font-size: 15px; color: {COLORS['body_grey']}; font-family: -apple-system, \"Segoe UI\", Arial, sans-serif; line-height: 1.6;'>{insights_str}</p>"
                else: # Plain string without bullets
                    processed_insights_html = f"<p style='margin: 12px 0 0 0; padding: 0; font-size: 15px; color: {COLORS['body_grey']}; font-family: -apple-system, \"Segoe UI\", Arial, sans-serif; line-height: 1.6;'>{insights_str}</p>"
            else: # Handles None, empty string, or empty list for insights
                processed_insights_html = "<p style='margin: 12px 0 0 0; padding: 0; font-size: 15px; color: " + COLORS['body_grey'] + "; font-family: -apple-system, \"Segoe UI\", Arial, sans-serif; line-height: 1.6;'>No analysis available for this article.</p>"

            # Alternating background for article content
            content_bg = COLORS['card_white'] if i % 2 == 1 else COLORS['background_grey']
            
            html_content += f"""\
                    <!-- Article {i} -->
                    <tr>
                        <td style="padding: 0 24px 16px 24px;">
                            <!-- Article card table -->
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="width: 100%; border: 1px solid {COLORS['border_grey']}; border-collapse: collapse; mso-table-lspace: 0pt; mso-table-rspace: 0pt;">
                                <tr>
                                    <!-- Red accent bar -->
                                    <td width="4" style="width: 4px; background-color: {COLORS['primary_red']}; font-size: 1px; line-height: 1px;">&nbsp;</td>
                                    <!-- Article content -->
                                    <td style="padding: 20px; background-color: {content_bg};">
                                        <!-- Title -->
                                        <h3 style="margin: 0 0 8px 0; padding: 0;">
                                            <a href="{url}" target="_blank" style="font-size: 17px; font-weight: bold; color: {COLORS['heading_black']}; text-decoration: none; font-family: -apple-system, 'Segoe UI', Arial, sans-serif; line-height: 1.3;">{i}. {title}</a>
                                        </h3>
                                        <!-- Meta info -->
                                        <p style="margin: 0 0 12px 0; padding: 0; font-size: 14px; color: {COLORS['meta_grey']}; font-family: -apple-system, 'Segoe UI', Arial, sans-serif; line-height: 1.4;">
                                            {source} &bull; {pub_time}
                                        </p>
                                        <!-- Insights -->
                                        {processed_insights_html}
                                        <!-- Read more link -->
                                        <p style="margin: 12px 0 0 0; padding: 0;">
                                            <a href="{url}" target="_blank" style="font-size: 14px; font-weight: bold; color: {COLORS['primary_red']}; text-decoration: none; font-family: -apple-system, 'Segoe UI', Arial, sans-serif;">Read Full Article &rarr;</a>
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
            """
        
        # Add footer with inline styling
        html_content += f"""\
                    <!-- Spacer row before footer -->
                    <tr>
                        <td style="height: 16px; font-size: 1px; line-height: 1px;">&nbsp;</td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px; border-top: 1px solid {COLORS['border_grey']}; background-color: {COLORS['footer_grey']}; text-align: center;">
                            <p style="margin: 0 0 12px 0; padding: 0; font-size: 14px; color: {COLORS['footer_text']}; font-family: -apple-system, 'Segoe UI', Arial, sans-serif; line-height: 1.5;">
                                This AI & Fintech News Digest is automatically generated. For a more comprehensive overview, the full report may be available as an attachment.
                            </p>
                            <p style="margin: 0 0 16px 0; padding: 0; font-size: 14px; color: {COLORS['footer_text']}; font-family: -apple-system, 'Segoe UI', Arial, sans-serif; line-height: 1.5;">
                                For feedback or inquiries, please reply to this email.
                            </p>
                            <p style="margin: 0; padding: 0; font-size: 13px; color: #9ca3af; font-family: -apple-system, 'Segoe UI', Arial, sans-serif;">&copy; {datetime.now().year} [Your Company Name]. All rights reserved.</p>
                        </td>
                    </tr>
                </table>
                <!-- End of main container -->
            </td>
        </tr>
    </table>
    <!-- End of outer wrapper -->
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