from src.news_scraper_simple import GoogleNewsScraper
from src.content_analyzer_simple import ContentAnalyzerSimple
from src.document_generator import DocumentGenerator
from datetime import datetime, timedelta
import os
from src.config import OUTPUT_DIR

def main():
    try:
        max_articles_per_keyword=100
        # Initialize the scraper
        scraper = GoogleNewsScraper(
            max_articles_per_keyword=max_articles_per_keyword,
            location='US',
            language='en'
        )

        # Define search parameters
        keywords = [
            'neural network development', 'OpenAI', 'Claude', 'LLM development',
            'fintech innovation', 'digital banking technology', 'blockchain finance',
            'AI in finance', 'AI in banking', 'AI in investment', 'AI in wealth management',
        ]
        
        # Set date range
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        print(f"\nFetching news from {start_date} to {end_date}")
        
        # Get news articles
        df = scraper.get_news(keywords, start_date, end_date, max_articles=max_articles_per_keyword*1000)
        df.to_excel('Output/news_articles.xlsx', index=False)

        if df.empty:
            print("No articles were found. Please check your search parameters.")
            return
            
        # Initialize analyzer and process articles
        analyzer = ContentAnalyzerSimple()
        articles = df.to_dict('records')
        
        # Process and analyze articles
        unique_articles = analyzer.remove_duplicates(articles)
        if not unique_articles:
            print("No unique articles found after duplicate removal.")
            return
            
        top_articles = analyzer.rank_articles(unique_articles, top_n=10)
        if not top_articles:
            print("No articles ranked high enough for analysis.")
            return
            
        topic_summary = analyzer.generate_topic_summary(top_articles)
        
        # Generate reports
        doc_generator = DocumentGenerator(llm_instance=analyzer.llm)
        brief_doc_path = doc_generator.generate_brief_summary(top_articles)
        detailed_doc_path = doc_generator.generate_detailed_report(top_articles)
        
        # Generate email content
        email_content = doc_generator.generate_email_content(top_articles)
        email_content_path = os.path.join(OUTPUT_DIR, f"email_content_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
        
        # Print results
        print("\nProcessing complete!")
        print(f"Brief summary: {brief_doc_path}")
        print(f"Detailed report: {detailed_doc_path}")
        print(f"\nCategory Breakdown for Top {len(top_articles)} Articles:")
        print(f"  AI Development: {topic_summary['ai_development_count']} articles")
        print(f"  Fintech: {topic_summary['fintech_count']} articles")
        print(f"  GenAI Usage: {topic_summary['genai_usage_count']} articles")
        print(f"  Other: {topic_summary['other_count']} articles")
        print(f"Email content saved to: {email_content_path}")
        print("You can now open this HTML file and copy its contents directly into your Outlook email.")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    main()