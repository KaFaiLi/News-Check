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
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from src.config import OPENAI_API_KEY, OPENAI_API_BASE, OUTPUT_DIR
from src.models import ArticleAnalysis, TrendAnalysis, BriefSummary, DetailedReport
from urllib.parse import urljoin
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class DocumentGenerator:
    def __init__(self, output_dir=OUTPUT_DIR, llm_instance: Optional[ChatOpenAI] = None):
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

    def generate_brief_summary(self, top_articles: List[Dict]):
        """Generates a brief Word document summary (e.g., top 3 articles)."""
        document = Document()
        self._set_doc_margins(document)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"brief_news_summary_{timestamp}.docx"
        filepath = os.path.join(self.output_dir, filename)

        self._add_styled_paragraph(document, "Brief News Summary", size=16, bold=True, alignment=WD_PARAGRAPH_ALIGNMENT.CENTER)
        self._add_styled_paragraph(document, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", size=10, alignment=WD_PARAGRAPH_ALIGNMENT.CENTER)
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

    def generate_detailed_report(self, top_articles: List[Dict]):
        """Generates a detailed Word document report including a table of contents."""
        document = Document()
        self._set_doc_margins(document)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"detailed_news_report_{timestamp}.docx"
        filepath = os.path.join(self.output_dir, filename)

        # Add title
        self._add_styled_paragraph(document, "Detailed News Report", size=16, bold=True, alignment=WD_PARAGRAPH_ALIGNMENT.CENTER)
        self._add_styled_paragraph(document, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", size=10, alignment=WD_PARAGRAPH_ALIGNMENT.CENTER)
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

    def generate_email_content(self, top_articles: List[Dict]) -> str:
        """Generates HTML content ready for copying into Outlook email."""
        
        # Generate timestamp
        timestamp = datetime.now().strftime('%A, %B %d, %Y')
        
        # Start building HTML content with email-client-friendly styling
        html_content = f"""
        <div style="font-family: Arial, sans-serif; font-size: 11pt; color: #000000; max-width: 800px;">
            <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse;">
                <tr>
                    <td style="padding: 20px 0; border-bottom: 2px solid #E9041E;">
                        <table width="100%" cellpadding="0" cellspacing="0">
                            <tr>
                                <td>
                                    <h2 style="font-size: 24pt; color: #000000; margin: 0; font-family: Arial, sans-serif;">AI & Fintech News Digest</h2>
                                    <p style="font-size: 11pt; color: #666666; margin: 5px 0;">{timestamp}</p>
                                </td>
                                <td align="right">
                                    <div style="background-color: #E9041E; color: white; padding: 5px 15px; display: inline-block;">
                                        <span style="font-size: 14pt;">Daily Briefing</span>
                                    </div>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
                
                <tr>
                    <td style="padding: 20px; background-color: #f8f9fa; border-left: 3px solid #E9041E; margin: 20px 0;">
                        <p style="margin: 0; color: #000000;">
                            Welcome to your daily AI and Fintech news briefing. Today's digest features the most significant 
                            developments in artificial intelligence, financial technology, and their industry applications. 
                            These carefully selected stories represent the most impactful developments in the last 24 hours.
                        </p>
                    </td>
                </tr>

                <tr>
                    <td style="padding: 20px 0;">
                        <table width="100%" cellpadding="0" cellspacing="0">
                            <tr>
                                <td>
                                    <h3 style="font-size: 14pt; color: #000000; margin: 0 0 20px 0; padding: 0;">
                                        <span style="border-left: 4px solid #E9041E; padding-left: 10px;">Today's Top Stories</span>
                                    </h3>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
        """
        
        # Add top 3 articles with email-client-friendly styling
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
                pub_time = pub_time_str
            
            insights = analysis.get('insights', 'No analysis available.')
            insights_str = str(insights) if insights else 'No analysis available.'
            
            # Use alternating background colors
            bg_color = '#f8f9fa' if i % 2 == 0 else '#ffffff'
            
            html_content += f"""
                <tr>
                    <td style="padding: 0 0 25px 0;">
                        <table width="100%" cellpadding="20" cellspacing="0" style="border: 1px solid #eeeeee; background-color: {bg_color};">
                            <tr>
                                <td style="border-left: 4px solid #E9041E;">
                                    <table width="100%" cellpadding="0" cellspacing="0">
                                        <tr>
                                            <td>
                                                <table width="100%" cellpadding="0" cellspacing="0">
                                                    <tr>
                                                        <td style="padding-right: 15px; width: 1%; white-space: nowrap;">
                                                            <span style="background-color: #E9041E; color: white; padding: 4px 12px; font-size: 11pt; display: inline-block;">News {i}</span>
                                                        </td>
                                                        <td width="99%">
                                                            <a href="{url}" style="color: #000000; text-decoration: none; font-weight: bold; font-size: 13pt;">{title}</a>
                                                        </td>
                                                    </tr>
                                                </table>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 10px 0;">
                                                <span style="color: #000000; font-weight: bold;">{source}</span>
                                                <span style="color: #666666; margin: 0 8px;">•</span>
                                                <span style="color: #666666;">{pub_time}</span>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="padding-top: 12px; border-top: 1px solid #eeeeee;">
                                                <div style="color: #000000; line-height: 1.6;">
                                                    {insights_str.replace('•', '<br>•').strip()}
                                                </div>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            """
        
        # Add footer with email-client-friendly styling
        html_content += """
                <tr>
                    <td style="padding: 20px 0; border-top: 1px solid #eeeeee; background-color: #f8f9fa;">
                        <table width="100%" cellpadding="0" cellspacing="0">
                            <tr>
                                <td style="padding-left: 20px; border-left: 4px solid #E9041E;">
                                    <p style="margin: 0; color: #000000; font-weight: bold;">About this digest</p>
                                    <p style="margin: 5px 0 0 0; color: #666666; font-size: 10pt;">This digest is auto-generated based on relevance and impact analysis.</p>
                                    <p style="margin: 5px 0 0 0; color: #666666; font-size: 10pt;">For any questions or feedback, please reply to this email.</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </div>
        """
        
        # Save the HTML content to a file for backup
        timestamp_file = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"email_content_{timestamp_file}.html"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        return html_content 