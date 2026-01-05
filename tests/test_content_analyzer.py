import unittest
from unittest.mock import patch, MagicMock
from src.content_analyzer_simple import ContentAnalyzerSimple

class TestContentAnalyzer(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.analyzer = ContentAnalyzerSimple()
        self.test_article = {
            'title': 'AI breakthrough in machine learning research',
            'snippet': 'New developments in artificial intelligence show promising results',
            'source': 'TechNews',
            'url': 'http://test.com',
            'published_time': '2024-03-01T12:00:00Z'
        }

    def test_analyze_article(self):
        """Test article analysis scoring."""
        analysis = self.analyzer.analyze_article(self.test_article)
        
        self.assertIsInstance(analysis, dict)
        self.assertIn('scores', analysis)
        self.assertIn('insights', analysis)
        self.assertIn('overall_score', analysis)
        
        # Check if AI Development category has high score due to keywords
        self.assertGreater(analysis['scores']['AI Development'], 0.5)

    def test_remove_duplicates(self):
        """Test duplicate article removal."""
        articles = [
            self.test_article,
            # Similar article
            {
                'title': 'AI breakthrough in ML research',
                'snippet': 'Different snippet',
                'source': 'OtherSource',
                'url': 'http://other.com'
            },
            # Different article
            {
                'title': 'Fintech innovations in banking',
                'snippet': 'New banking technologies',
                'source': 'FinNews',
                'url': 'http://fin.com'
            }
        ]
        
        unique_articles = self.analyzer.remove_duplicates(articles)
        self.assertEqual(len(unique_articles), 2)  # Should remove one duplicate

    @patch('langchain_openai.AzureChatOpenAI')
    def test_get_llm_insights(self, mock_llm):
        """Test LLM insights generation."""
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = "Test insight about AI breakthrough"
        mock_llm.return_value.invoke.return_value = mock_response
        
        insights = self.analyzer.get_llm_insights(self.test_article)
        self.assertIsInstance(insights, str)

    def test_rank_articles(self):
        """Test article ranking."""
        articles = [
            self.test_article,
            {
                'title': 'Weather forecast',
                'snippet': 'Tomorrow will be sunny',
                'source': 'WeatherNews',
                'url': 'http://weather.com'
            }
        ]
        
        ranked_articles = self.analyzer.rank_articles(articles, top_n=2)
        self.assertEqual(len(ranked_articles), 2)
        
        # AI article should be ranked higher due to relevance
        first_article = ranked_articles[0]['article']['title']
        self.assertIn('AI', first_article)

    def test_calculate_trending_score(self):
        """Test trending score calculation."""
        articles = [self.test_article] * 3  # Create multiple similar articles
        
        trending_score = self.analyzer.calculate_trending_score(
            self.test_article,
            articles
        )
        
        self.assertIsInstance(trending_score, float)
        self.assertGreaterEqual(trending_score, 0.0)
        self.assertLessEqual(trending_score, 1.0)

if __name__ == '__main__':
    unittest.main() 