import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import pandas as pd
from src.news_scraper_simple import GoogleNewsScraper

class TestGoogleNewsScraper(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.scraper = GoogleNewsScraper(max_articles_per_keyword=5)
        self.test_keywords = ['test keyword']
        self.end_date = datetime.now().strftime('%Y-%m-%d')
        self.start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    def test_init(self):
        """Test scraper initialization."""
        self.assertEqual(self.scraper.max_articles_per_keyword, 5)
        self.assertEqual(self.scraper.location, 'US')
        self.assertEqual(self.scraper.language, 'en')
        self.assertTrue('User-Agent' in self.scraper.headers)

    def test_format_date_for_tbs(self):
        """Test date formatting."""
        test_date = '2024-03-01'
        expected = '03/01/2024'
        result = self.scraper._format_date_for_tbs(test_date)
        self.assertEqual(result, expected)

        # Test invalid date format
        with self.assertRaises(ValueError):
            self.scraper._format_date_for_tbs('invalid-date')

    def test_parse_relative_time(self):
        """Test relative time parsing."""
        test_cases = [
            ('1 hour ago', timedelta(hours=1)),
            ('2 days ago', timedelta(days=2)),
            ('30 minutes ago', timedelta(minutes=30)),
            ('yesterday', timedelta(days=1)),
        ]

        for time_str, expected_delta in test_cases:
            parsed_time = self.scraper._parse_relative_time(time_str)
            self.assertIsNotNone(parsed_time)
            # Allow for small time differences in test execution
            time_diff = abs((datetime.now(parsed_time.tzinfo) - parsed_time) - expected_delta)
            self.assertTrue(time_diff.total_seconds() < 5)  # Within 5 seconds tolerance

    @patch('requests.get')
    def test_get_news_success(self, mock_get):
        """Test successful news fetching."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
        <div class="SoaBEf">
            <div class="n0jPhd ynAwRc MBeuO nDgy9d">Test Title</div>
            <div class="MgUUmf NUnG9d">Test Source</div>
            <div class="GI74Re nDgy9d">Test Snippet</div>
            <a href="http://test.com">Link</a>
            <span class="">1 hour ago</span>
        </div>
        '''
        mock_get.return_value = mock_response

        df = self.scraper.get_news(
            self.test_keywords,
            self.start_date,
            self.end_date,
            max_articles=1
        )

        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        if not df.empty:
            self.assertEqual(df.iloc[0]['title'], 'Test Title')
            self.assertEqual(df.iloc[0]['source'], 'Test Source')

    @patch('requests.get')
    def test_get_news_failure(self, mock_get):
        """Test news fetching with failed request."""
        # Mock failed response
        mock_get.side_effect = Exception('Network error')

        df = self.scraper.get_news(
            self.test_keywords,
            self.start_date,
            self.end_date,
            max_articles=1
        )

        self.assertIsInstance(df, pd.DataFrame)
        self.assertTrue(df.empty)

    @patch('requests.get')
    def test_get_news_captcha(self, mock_get):
        """Test handling of CAPTCHA response."""
        # Mock CAPTCHA response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = 'captcha'
        mock_get.return_value = mock_response

        df = self.scraper.get_news(
            self.test_keywords,
            self.start_date,
            self.end_date,
            max_articles=1
        )

        self.assertIsInstance(df, pd.DataFrame)
        self.assertTrue(df.empty)

if __name__ == '__main__':
    unittest.main() 