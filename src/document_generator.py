"""Module for generating Word documents with news summaries."""

import os
from datetime import datetime
from typing import List, Dict
import requests
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from config import OPENAI_API_KEY, OPENAI_API_BASE, OUTPUT_DIR
from models import ArticleAnalysis, TrendAnalysis, BriefSummary, DetailedReport

class DocumentGenerator:
    def __init__(self, output_dir='Output'):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def generate_brief_summary(self, articles):
        """Generate a brief summary document with top 3 articles"""
        doc = Document()
        
        # Add title
        title = doc.add_heading('News Summary Report', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add date
        date_paragraph = doc.add_paragraph()
        date_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        date_paragraph.add_run(f'Generated on {datetime.now().strftime("%B %d, %Y")}')
        
        doc.add_paragraph('\n')
        
        # Add top articles
        doc.add_heading('Top Stories', level=1)
        for idx, article in enumerate(articles[:3], 1):
            # Add article title
            doc.add_heading(f'{idx}. {article["article"]["title"]}', level=2)
            
            # Add metadata
            meta = doc.add_paragraph(style='Intense Quote')
            meta.add_run(f'Source: {article["article"].get("source", "Unknown")}\n')
            meta.add_run(f'Date: {article["article"].get("published_time", "Unknown")}\n')
            meta.add_run(f'Category: {max(article["analysis"]["scores"].items(), key=lambda x: x[1])[0]}')
            
            # Add description and insights
            doc.add_paragraph(article["article"].get("description", "No description available"))
            if article["analysis"].get("insights"):
                doc.add_paragraph(article["analysis"]["insights"], style='Quote')
            
            doc.add_paragraph('\n')
        
        # Save document
        output_path = os.path.join(self.output_dir, 'brief_summary.docx')
        doc.save(output_path)
        return output_path

    def generate_detailed_report(self, articles):
        """Generate a detailed report with top 10 articles and analysis"""
        doc = Document()
        
        # Add title
        title = doc.add_heading('Detailed News Analysis Report', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add date
        date_paragraph = doc.add_paragraph()
        date_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        date_paragraph.add_run(f'Generated on {datetime.now().strftime("%B %d, %Y")}')
        
        doc.add_paragraph('\n')
        
        # Add category distribution
        doc.add_heading('Category Distribution', level=1)
        categories = {'AI Development': 0, 'Fintech': 0, 'GenAI Usage': 0}
        for article in articles:
            category = max(article["analysis"]["scores"].items(), key=lambda x: x[1])[0]
            categories[category] += 1
        
        for category, count in categories.items():
            doc.add_paragraph(f'{category}: {count} articles')
        
        doc.add_paragraph('\n')
        
        # Add detailed article analysis
        doc.add_heading('Detailed Article Analysis', level=1)
        for idx, article in enumerate(articles[:10], 1):
            # Add article title
            doc.add_heading(f'{idx}. {article["article"]["title"]}', level=2)
            
            # Add metadata
            meta = doc.add_paragraph(style='Intense Quote')
            meta.add_run(f'Source: {article["article"].get("source", "Unknown")}\n')
            meta.add_run(f'Date: {article["article"].get("published_time", "Unknown")}\n')
            
            # Add category scores
            doc.add_heading('Category Relevance', level=3)
            for category, score in article["analysis"]["scores"].items():
                doc.add_paragraph(f'{category}: {score:.2%}')
            
            # Add description and insights
            doc.add_heading('Content', level=3)
            doc.add_paragraph(article["article"].get("description", "No description available"))
            
            if article["analysis"].get("insights"):
                doc.add_heading('Analysis', level=3)
                doc.add_paragraph(article["analysis"]["insights"], style='Quote')
            
            doc.add_paragraph('\n')
        
        # Save document
        output_path = os.path.join(self.output_dir, 'detailed_report.docx')
        doc.save(output_path)
        return output_path 