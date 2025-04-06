from src.news_scraper_simple import GoogleNewsScraper
from src.content_analyzer_simple import ContentAnalyzerSimple
from src.document_generator import DocumentGenerator
from datetime import datetime, timedelta
import os

def main():
    try:
        # Initialize the scraper
        scraper = GoogleNewsScraper(
            max_articles_per_keyword=25,
            location='US',
            language='en'
        )

        # Define search parameters
        keywords = [
            'artificial intelligence research', 'machine learning breakthrough', 'neural network development',
            'fintech innovation', 'digital banking technology', 'blockchain finance',
            'generative AI', 'ChatGPT enterprise', 'AI content creation'
        ]
        
        # Set date range
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        print(f"\nFetching news from {start_date} to {end_date}")
        
        # Get news articles
        df = scraper.get_news(keywords, start_date, end_date, max_articles=100)
        
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
            
        top_articles = analyzer.rank_articles(unique_articles, top_n=20)
        if not top_articles:
            print("No articles ranked high enough for analysis.")
            return
            
        topic_summary = analyzer.generate_topic_summary(top_articles)
        
        # Generate reports
        doc_generator = DocumentGenerator(llm_instance=analyzer.llm)
        brief_doc_path = doc_generator.generate_brief_summary(top_articles)
        detailed_doc_path = doc_generator.generate_detailed_report(top_articles)
        
        # Print results
        print("\nProcessing complete!")
        print(f"Brief summary: {brief_doc_path}")
        print(f"Detailed report: {detailed_doc_path}")
        print(f"\nCategory Breakdown for Top {len(top_articles)} Articles:")
        print(f"  AI Development: {topic_summary['ai_development_count']} articles")
        print(f"  Fintech: {topic_summary['fintech_count']} articles")
        print(f"  GenAI Usage: {topic_summary['genai_usage_count']} articles")
        print(f"  Other: {topic_summary['other_count']} articles")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    main()