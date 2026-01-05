"""Tests for graceful degradation functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.models import DegradationStatus


class TestDegradationStatus:
    """Test DegradationStatus model and methods."""
    
    def test_initial_status(self):
        """Test initial degradation status."""
        status = DegradationStatus()
        assert status.is_degraded is False
        assert status.total_attempts == 0
        assert status.successful_attempts == 0
        assert status.failed_attempts == 0
        assert status.consecutive_failures == 0
        assert status.success_rate == 1.0
        assert status.collected_results_count == 0
        assert status.warnings == []
    
    def test_update_success(self):
        """Test updating status after successful attempt."""
        status = DegradationStatus()
        status.update_success()
        
        assert status.total_attempts == 1
        assert status.successful_attempts == 1
        assert status.failed_attempts == 0
        assert status.consecutive_failures == 0
        assert status.success_rate == 1.0
    
    def test_update_failure(self):
        """Test updating status after failed attempt."""
        status = DegradationStatus()
        warning = "Test failure"
        status.update_failure(warning)
        
        assert status.total_attempts == 1
        assert status.successful_attempts == 0
        assert status.failed_attempts == 1
        assert status.consecutive_failures == 1
        assert status.success_rate == 0.0
        assert warning in status.warnings
    
    def test_consecutive_failures_reset_on_success(self):
        """Test that consecutive failures reset after success."""
        status = DegradationStatus()
        status.update_failure("Failure 1")
        status.update_failure("Failure 2")
        assert status.consecutive_failures == 2
        
        status.update_success()
        assert status.consecutive_failures == 0
    
    def test_success_rate_calculation(self):
        """Test success rate calculation with mixed results."""
        status = DegradationStatus()
        status.update_success()
        status.update_success()
        status.update_failure()
        status.update_success()
        status.update_failure()
        
        # 3 successful, 2 failed out of 5 total
        assert status.total_attempts == 5
        assert status.successful_attempts == 3
        assert status.failed_attempts == 2
        assert status.success_rate == 0.6
    
    def test_check_degradation_threshold_by_rate(self):
        """Test degradation threshold check based on success rate."""
        status = DegradationStatus()
        min_threshold = 0.6
        max_consecutive = 3
        
        # Below threshold (40% success rate)
        status.update_success()
        status.update_failure()
        status.update_failure()
        status.update_failure()
        status.update_failure()
        
        is_degraded = status.check_degradation_threshold(min_threshold, max_consecutive)
        assert is_degraded is True
        assert status.is_degraded is True
    
    def test_check_degradation_threshold_by_consecutive(self):
        """Test degradation threshold check based on consecutive failures."""
        status = DegradationStatus()
        min_threshold = 0.6
        max_consecutive = 3
        
        # 3 consecutive failures triggers degradation
        status.update_failure()
        status.update_failure()
        status.update_failure()
        
        is_degraded = status.check_degradation_threshold(min_threshold, max_consecutive)
        assert is_degraded is True
        assert status.is_degraded is True
    
    def test_no_degradation_above_threshold(self):
        """Test that degradation is not triggered when above threshold."""
        status = DegradationStatus()
        min_threshold = 0.6
        max_consecutive = 3
        
        # 70% success rate, only 1 consecutive failure
        status.update_success()
        status.update_success()
        status.update_success()
        status.update_success()
        status.update_success()
        status.update_success()
        status.update_success()
        status.update_failure()
        status.update_success()
        status.update_success()
        
        is_degraded = status.check_degradation_threshold(min_threshold, max_consecutive)
        assert is_degraded is False
        assert status.is_degraded is False


class TestNewsScraperDegradation:
    """Test degradation handling in news scraper."""
    
    @patch('src.news_scraper_simple.requests.get')
    def test_scraper_tracks_success(self, mock_get):
        """Test that scraper tracks successful fetches."""
        from src.news_scraper_simple import GoogleNewsScraper
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<html><div class="SoaBEf"></div></html>'
        mock_get.return_value = mock_response
        
        scraper = GoogleNewsScraper(max_articles_per_keyword=5)
        initial_status = scraper.degradation_status
        
        assert initial_status.total_attempts == 0
        assert initial_status.is_degraded is False
    
    def test_scraper_initializes_degradation_status(self):
        """Test that scraper initializes with degradation tracking."""
        from src.news_scraper_simple import GoogleNewsScraper
        
        scraper = GoogleNewsScraper(max_articles_per_keyword=5)
        
        assert hasattr(scraper, 'degradation_status')
        assert isinstance(scraper.degradation_status, DegradationStatus)
        assert scraper.enable_graceful_degradation is True


class TestContentAnalyzerDegradation:
    """Test degradation handling in content analyzer."""
    
    def test_analyzer_initializes_degradation_status(self):
        """Test that content analyzer initializes with degradation tracking."""
        from src.content_analyzer_simple import ContentAnalyzerSimple
        
        analyzer = ContentAnalyzerSimple()
        
        assert hasattr(analyzer, 'degradation_status')
        assert isinstance(analyzer.degradation_status, DegradationStatus)


class TestDocumentGeneratorDegradation:
    """Test degradation warnings in document generator."""
    
    def test_brief_summary_with_degradation_warning(self):
        """Test that brief summary includes degradation warning."""
        from src.document_generator import DocumentGenerator
        from src.models import DegradationStatus
        from src.config import INCLUDE_DEGRADATION_WARNING
        
        if not INCLUDE_DEGRADATION_WARNING:
            pytest.skip("Degradation warnings disabled in config")
        
        generator = DocumentGenerator()
        
        # Create degraded status
        status = DegradationStatus()
        status.is_degraded = True
        status.total_attempts = 10
        status.successful_attempts = 4
        status.failed_attempts = 6
        status.success_rate = 0.4
        status.warnings = ["Test warning 1", "Test warning 2"]
        
        # Mock articles
        articles = [
            {
                'article': {
                    'title': 'Test Article',
                    'source': 'Test Source',
                    'published_time': '2026-01-05T10:00:00',
                    'url': 'https://test.com'
                },
                'analysis': {
                    'insights': 'Test insights'
                }
            }
        ]
        
        # Generate document
        filepath = generator.generate_brief_summary(articles, status)
        assert filepath.endswith('.docx')
    
    def test_detailed_report_with_degradation_warning(self):
        """Test that detailed report includes degradation warning."""
        from src.document_generator import DocumentGenerator
        from src.models import DegradationStatus
        from src.config import INCLUDE_DEGRADATION_WARNING
        
        if not INCLUDE_DEGRADATION_WARNING:
            pytest.skip("Degradation warnings disabled in config")
        
        generator = DocumentGenerator()
        
        # Create degraded status
        status = DegradationStatus()
        status.is_degraded = True
        status.total_attempts = 10
        status.successful_attempts = 4
        status.failed_attempts = 6
        status.success_rate = 0.4
        status.warnings = ["Test warning 1", "Test warning 2"]
        
        # Mock articles
        articles = [
            {
                'article': {
                    'title': 'Test Article',
                    'source': 'Test Source',
                    'published_time': '2026-01-05T10:00:00',
                    'url': 'https://test.com'
                },
                'analysis': {
                    'insights': 'Test insights'
                }
            }
        ]
        
        # Generate document
        filepath = generator.generate_detailed_report(articles, status)
        assert filepath.endswith('.docx')
    
    def test_email_content_with_degradation_warning(self):
        """Test that email content includes degradation warning."""
        from src.document_generator import DocumentGenerator
        from src.models import DegradationStatus
        from src.config import INCLUDE_DEGRADATION_WARNING
        
        if not INCLUDE_DEGRADATION_WARNING:
            pytest.skip("Degradation warnings disabled in config")
        
        generator = DocumentGenerator()
        
        # Create degraded status
        status = DegradationStatus()
        status.is_degraded = True
        status.total_attempts = 10
        status.successful_attempts = 4
        status.failed_attempts = 6
        status.success_rate = 0.4
        status.collected_results_count = 5
        
        # Mock articles
        articles = [
            {
                'article': {
                    'title': 'Test Article',
                    'source': 'Test Source',
                    'published_time': '2026-01-05T10:00:00',
                    'url': 'https://test.com'
                },
                'analysis': {
                    'insights': 'Test insights'
                }
            }
        ]
        
        # Generate email content
        html = generator.generate_email_content(articles, status)
        assert 'DEGRADATION WARNING' in html
        assert '40.0%' in html or '40%' in html  # Success rate formatting
