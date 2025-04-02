import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from news_scraper import GoogleNewsScraper
from content_analyzer import ContentAnalyzer
from email_generator import EmailGenerator

# Load environment variables
load_dotenv()

class AINewsUpdateSystem:
    def __init__(self):
        self.scraper = GoogleNewsScraper()
        self.analyzer = ContentAnalyzer()
        self.email_generator = EmailGenerator()
        
        # AI-focused search terms
        self.search_terms = [
            'AI banking regulation',
            'Generative AI financial services',
            'AI compliance banking',
            'AI investment banking use cases',
            'Banking AI implementation',
            'AI risk management banking',
            'AI audit financial services',
            'AI regulatory compliance banking'
        ]

    def get_date_range(self):
        """Get date range for the current quarter"""
        today = datetime.now()
        current_quarter = (today.month - 1) // 3
        quarter_start = datetime(today.year, 3 * current_quarter + 1, 1)
        quarter_end = today
        return quarter_start.strftime('%Y-%m-%d'), quarter_end.strftime('%Y-%m-%d')

    def run_quarterly_update(self):
        """Execute the quarterly news update process"""
        try:
            print("Starting quarterly AI news update process...")
            
            # 1. Collect news articles
            start_date, end_date = self.get_date_range()
            all_articles = []
            
            for term in self.search_terms:
                print(f"Scraping news for term: {term}")
                articles = self.scraper.scrape_news([term], start_date, end_date)
                all_articles.extend(articles.to_dict('records'))
                
            print(f"Total articles collected: {len(all_articles)}")

            # 2. Remove duplicates
            unique_articles = self.analyzer.remove_duplicates(all_articles)
            print(f"Unique articles after deduplication: {len(unique_articles)}")

            # 3. Analyze and rank articles
            top_articles = self.analyzer.rank_articles(unique_articles)
            print(f"Selected top {len(top_articles)} articles")

            # 4. Generate quarterly summary
            summary_data = self.analyzer.generate_quarterly_summary(top_articles)
            print("Generated quarterly summary")

            # 5. Generate newsletter content
            html_content = self.email_generator.generate_newsletter(summary_data)
            
            # 6. Save output files
            self._save_output(summary_data, html_content)
            print("Process completed successfully. Check the output directory for the generated files.")

        except Exception as e:
            print(f"Error in quarterly update process: {str(e)}")
            raise

            print(f"Total articles collected: {len(all_articles)}")

            # 2. Remove duplicates
            unique_articles = self.analyzer.remove_duplicates(all_articles)
            print(f"Unique articles after deduplication: {len(unique_articles)}")

            # 3. Analyze and rank articles
            top_articles = self.analyzer.rank_articles(unique_articles)
            print(f"Selected top {len(top_articles)} articles")

            # 4. Generate quarterly summary
            summary_data = self.analyzer.generate_quarterly_summary(top_articles)
            print("Generated quarterly summary")

            # 5. Generate and send newsletter
            html_content = self.email_generator.generate_newsletter(summary_data)
            
            recipients = os.getenv('NEWSLETTER_RECIPIENTS', '').split(',')
            if recipients:
                success = self.email_generator.send_newsletter(recipients, html_content)
                if success:
                    print("Newsletter sent successfully")
                else:
                    print("Failed to send newsletter")
            else:
                print("No recipients configured")

            # 6. Save output
            self._save_output(summary_data)
            print("Process completed successfully")

        except Exception as e:
            print(f"Error in quarterly update process: {str(e)}")
            raise

    def _save_output(self, summary_data, html_content):
        """Save the quarterly update output to files"""
        os.makedirs('output', exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save summary to text file (Outlook-friendly format)
        with open(f'output/quarterly_summary_{timestamp}.txt', 'w') as f:
            f.write("Subject: Quarterly AI Development Update - Top 10 Insights\n\n")
            f.write("Executive Summary:\n")
            f.write("=================\n")
            f.write("\n".join(f"• {point}" for point in summary_data['executive_summary']))
            f.write("\n\nTop Articles:\n")
            f.write("============\n")
            for article in summary_data['top_articles']:
                f.write(f"\n{article['title']}\n")
                f.write("-" * len(article['title']) + "\n")
                f.write(f"Source: {article.get('source', 'Unknown')}\n")
                f.write(f"URL: {article.get('url', 'N/A')}\n\n")
                f.write("Key Points:\n")
                for point in article['analysis'].key_points:
                    f.write(f"• {point}\n")
                f.write("\nWhy It Matters to Banking Auditors:\n")
                f.write(f"{article['analysis'].banking_relevance}\n\n")
                f.write("-" * 80 + "\n")
        
        # Save HTML version
        with open(f'output/newsletter_{timestamp}.html', 'w') as f:
            f.write(html_content)

def main():
    # Set up environment variables
    if not os.getenv('OPENAI_API_KEY'):
        print("Missing required environment variable: OPENAI_API_KEY")
        print("Please set this variable in your .env file")
        return

    system = AINewsUpdateSystem()
    system.run_quarterly_update()

if __name__ == '__main__':
    main()