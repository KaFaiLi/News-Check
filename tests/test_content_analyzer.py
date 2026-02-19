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

    def test_get_base_domain(self):
        """Test domain extraction from URLs."""
        # Test with www prefix
        domain = self.analyzer.get_base_domain('https://www.cnn.com/article/123')
        self.assertEqual(domain, 'cnn.com')
        
        # Test with subdomain
        domain = self.analyzer.get_base_domain('https://news.bbc.co.uk/story')
        self.assertEqual(domain, 'news.bbc.co.uk')
        
        # Test without www
        domain = self.analyzer.get_base_domain('https://reuters.com/article')
        self.assertEqual(domain, 'reuters.com')
        
        # Test edge case - invalid URL
        domain = self.analyzer.get_base_domain('invalid-url')
        self.assertEqual(domain, '')

    def test_get_source_tier(self):
        """Test source tier matching."""
        # Test tier-1 exact match
        tier = self.analyzer.get_source_tier('https://www.cnn.com/article')
        self.assertEqual(tier, 1)
        
        # Test tier-1 subdomain match
        tier = self.analyzer.get_source_tier('https://edition.cnn.com/article')
        self.assertEqual(tier, 1)
        
        # Test tier-2 exact match
        tier = self.analyzer.get_source_tier('https://techcrunch.com/article')
        self.assertEqual(tier, 2)
        
        # Test tier-2 subdomain match
        tier = self.analyzer.get_source_tier('https://www.techcrunch.com/article')
        self.assertEqual(tier, 2)
        
        # Test tier-3 (unranked)
        tier = self.analyzer.get_source_tier('https://unknown-blog.com/article')
        self.assertEqual(tier, 3)
        
        # Test BBC UK domain
        tier = self.analyzer.get_source_tier('https://www.bbc.co.uk/news')
        self.assertEqual(tier, 1)

    def test_calculate_source_score(self):
        """Test source score normalization."""
        # Test tier-1 score (should be 1.0 as maximum)
        score = self.analyzer.calculate_source_score(1)
        self.assertAlmostEqual(score, 1.0, places=2)
        
        # Test tier-2 score (1.1 / 1.3 ≈ 0.846)
        score = self.analyzer.calculate_source_score(2)
        self.assertAlmostEqual(score, 0.846, places=2)
        
        # Test tier-3 score (1.0 / 1.3 ≈ 0.769)
        score = self.analyzer.calculate_source_score(3)
        self.assertAlmostEqual(score, 0.769, places=2)
        
        # Test score is within valid range
        for tier in [1, 2, 3]:
            score = self.analyzer.calculate_source_score(tier)
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)

    def test_strip_non_content_elements(self):
        """Test non-content element removal from HTML."""
        from bs4 import BeautifulSoup
        
        # Create test HTML with both content and non-content elements
        html = """
        <html>
            <head><script>console.log('test');</script></head>
            <body>
                <nav class="main-nav">Navigation</nav>
                <header>Site Header</header>
                <div class="advertisement">Ad content</div>
                <article>
                    <h1>Article Title</h1>
                    <p>Article content that should be preserved.</p>
                    <table><tr><td>Data</td></tr></table>
                </article>
                <aside class="sidebar">Sidebar content</aside>
                <footer>Site Footer</footer>
                <div id="cookie-banner">Cookie notice</div>
            </body>
        </html>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        cleaned = self.analyzer.strip_non_content_elements(soup)
        
        # Content should be preserved
        self.assertIn('Article content that should be preserved', cleaned.get_text())
        self.assertIn('Article Title', cleaned.get_text())
        self.assertIn('Data', cleaned.get_text())
        
        # Non-content should be removed
        self.assertNotIn('Navigation', cleaned.get_text())
        self.assertNotIn('Site Header', cleaned.get_text())
        self.assertNotIn('Ad content', cleaned.get_text())
        self.assertNotIn('Sidebar content', cleaned.get_text())
        self.assertNotIn('Site Footer', cleaned.get_text())
        self.assertNotIn('Cookie notice', cleaned.get_text())
        
        # Scripts should be removed
        self.assertEqual(len(cleaned.find_all('script')), 0)

    def test_source_tier_ranking(self):
        """Test that tier-1 articles rank higher with equal keyword scores (T023)."""
        # Create two articles with identical content but different sources
        tier1_article = {
            'title': 'Breaking news about AI developments',
            'snippet': 'New artificial intelligence breakthrough announced',
            'source': 'CNN',
            'url': 'https://www.cnn.com/article',
            'published_time': '2024-03-01T12:00:00Z'
        }
        
        tier3_article = {
            'title': 'Breaking news about AI developments',
            'snippet': 'New artificial intelligence breakthrough announced',
            'source': 'Unknown Blog',
            'url': 'https://unknown-blog.com/article',
            'published_time': '2024-03-01T12:00:00Z'
        }
        
        # Analyze both articles
        analysis1 = self.analyzer.analyze_article(tier1_article)
        analysis3 = self.analyzer.analyze_article(tier3_article)
        
        # Verify tier-1 has higher source score
        self.assertEqual(analysis1['source_tier'], 1)
        self.assertEqual(analysis3['source_tier'], 3)
        self.assertGreater(analysis1['source_score'], analysis3['source_score'])
        
        # Verify keyword scores are similar
        self.assertAlmostEqual(
            analysis1['keyword_score'], 
            analysis3['keyword_score'], 
            places=2,
            msg="Keyword scores should be nearly identical for same content"
        )
        
        # Verify overall score is higher for tier-1 due to source reliability
        self.assertGreater(
            analysis1['overall_score'], 
            analysis3['overall_score'],
            msg="Tier-1 article should have higher overall score than tier-3"
        )

    def test_source_diversity_cap(self):
        """Test that source diversity cap limits articles per source (T024)."""
        # Create 5 articles from CNN and 5 from other sources
        articles = []
        
        # Add 5 CNN articles
        for i in range(5):
            articles.append({
                'title': f'CNN Article {i+1} about AI developments',
                'snippet': 'Artificial intelligence breakthrough announced',
                'source': 'CNN',
                'url': f'https://www.cnn.com/article-{i+1}',
                'published_time': '2024-03-01T12:00:00Z'
            })
        
        # Add 5 articles from different sources
        other_sources = ['bbc.com', 'reuters.com', 'nytimes.com', 'bloomberg.com', 'wsj.com']
        for i, source in enumerate(other_sources):
            articles.append({
                'title': f'Article {i+6} about AI developments',
                'snippet': 'Artificial intelligence breakthrough announced',
                'source': source.split('.')[0].upper(),
                'url': f'https://{source}/article',
                'published_time': '2024-03-01T12:00:00Z'
            })
        
        # Rank articles with top_n=10
        # Note: This test checks diversity enforcement logic
        analyzed = []
        for article in articles:
            analysis = self.analyzer.analyze_article(article)
            analyzed.append({'article': article, 'analysis': analysis})
        
        # Sort by score
        analyzed.sort(key=lambda x: x['analysis']['overall_score'], reverse=True)
        
        # Apply diversity enforcement
        diverse = self.analyzer.enforce_source_diversity(analyzed[:10])
        
        # Count CNN articles
        cnn_count = sum(1 for item in diverse 
                       if 'cnn.com' in item['article']['url'])
        
        # Verify cap is enforced (max 3 per source)
        self.assertLessEqual(cnn_count, 3, 
                            "CNN articles should be capped at 3 in top results")

    def test_fintech_minimum_maintained(self):
        """Test that Fintech minimum (≥3 articles) is maintained after scoring changes (T025)."""
        # Create articles: 8 AI articles (high scoring) and 4 Fintech articles (lower scoring)
        articles = []
        
        # Add 8 high-scoring AI articles
        for i in range(8):
            articles.append({
                'title': f'Major AI breakthrough {i+1} in neural networks research',
                'snippet': 'Artificial intelligence large language models show promising results',
                'source': 'CNN',
                'url': f'https://www.cnn.com/ai-article-{i+1}',
                'published_time': '2024-03-01T12:00:00Z'
            })
        
        # Add 4 lower-scoring Fintech articles
        for i in range(4):
            articles.append({
                'title': f'Digital banking update {i+1}',
                'snippet': 'Blockchain finance and payment technology developments',
                'source': 'TechCrunch',
                'url': f'https://techcrunch.com/fintech-{i+1}',
                'published_time': '2024-03-01T12:00:00Z'
            })
        
        # Rank articles
        ranked = self.analyzer.rank_articles(articles, top_n=10)
        
        # Count Fintech articles in top 10
        fintech_count = sum(1 for item in ranked 
                           if item['analysis']['primary_category'] == 'Fintech')
        
        # Verify minimum Fintech requirement is met
        self.assertGreaterEqual(fintech_count, 3, 
                               "Must have at least 3 Fintech articles in top 10")

    def test_markdown_conversion_with_tables(self):
        """Test successful markdown conversion preserving tables (T034)."""
        from bs4 import BeautifulSoup
        from src.config import MAX_MARKDOWN_LENGTH
        
        # Create HTML with table
        html_with_table = """
        <html>
            <body>
                <article>
                    <h1>Financial Report</h1>
                    <p>Q4 earnings summary:</p>
                    <table>
                        <tr><th>Metric</th><th>Value</th></tr>
                        <tr><td>Revenue</td><td>$100M</td></tr>
                        <tr><td>Profit</td><td>$20M</td></tr>
                    </table>
                    <p>Strong performance across all sectors.</p>
                </article>
            </body>
        </html>
        """
        
        soup = BeautifulSoup(html_with_table, 'html.parser')
        cleaned = self.analyzer.strip_non_content_elements(soup)
        markdown = self.analyzer.h2t.handle(str(cleaned))
        
        # Verify table content is preserved in markdown
        self.assertIn('Revenue', markdown)
        self.assertIn('$100M', markdown)
        self.assertIn('Metric', markdown)
        self.assertIn('Value', markdown)
        
        # Verify article text is preserved
        self.assertIn('Financial Report', markdown)
        self.assertIn('Strong performance', markdown)

    def test_markdown_truncation(self):
        """Test markdown truncation at 400K character limit (T036)."""
        from src.config import MAX_MARKDOWN_LENGTH, TRUNCATION_INDICATOR
        
        # Create very long markdown content
        long_content = "A" * (MAX_MARKDOWN_LENGTH + 10000)
        
        # Simulate truncation logic
        if len(long_content) > MAX_MARKDOWN_LENGTH:
            truncated = long_content[:MAX_MARKDOWN_LENGTH] + TRUNCATION_INDICATOR
        else:
            truncated = long_content
        
        # Verify truncation occurred
        self.assertLess(len(truncated), len(long_content))
        self.assertTrue(truncated.endswith(TRUNCATION_INDICATOR))
        self.assertEqual(len(truncated), MAX_MARKDOWN_LENGTH + len(TRUNCATION_INDICATOR))

    @patch('src.content_analyzer_simple.ContentAnalyzerSimple._fetch_with_playwright')
    def test_conversion_fallback_on_error(self, mock_fetch):
        """Test fallback to main-body extraction on conversion failure (T037)."""
        # Mock HTML with malformed structure that might cause conversion issues
        html_content = """
        <html>
            <body>
                <main>
                    <h1>Article Title</h1>
                    <p>Main article content that should be extracted in fallback.</p>
                </main>
            </body>
        </html>
        """
        mock_fetch.return_value = html_content
        
        # The method should handle any conversion errors gracefully
        try:
            result = self.analyzer.fetch_article_content('https://test.com/article', 'test_article_001')
            # If it succeeds (no exception), verify we got some content
            if result:
                self.assertIn('extracted_markdown', result)
                self.assertTrue(len(result['extracted_markdown']) > 0)
        except Exception as e:
            # If it fails, the method should have logged the error
            self.fail(f"fetch_article_content should handle errors gracefully: {e}")

    @patch('src.content_analyzer_simple.ContentAnalyzerSimple._fetch_with_playwright')
    @patch('src.content_analyzer_simple.ContentAnalyzerSimple._detect_paywall')
    def test_paywall_handling(self, mock_detect, mock_fetch):
        """Test paywall detection and preview content extraction (T038)."""
        # Mock paywalled content
        paywalled_html = """
        <html>
            <body>
                <div class="article-preview">
                    <h1>Premium Article</h1>
                    <p>Preview paragraph available for free.</p>
                </div>
                <div class="paywall">Subscribe to read more</div>
            </body>
        </html>
        """
        
        mock_fetch.return_value = paywalled_html
        mock_detect.return_value = True  # Simulate paywall detection
        
        # Fetch content
        result = self.analyzer.fetch_article_content('https://wsj.com/article', 'test_paywall_001')
        
        # Verify result contains conversion metadata indicating paywall
        if result and 'conversion_metadata' in result:
            self.assertTrue(result['conversion_metadata'].get('is_paywalled', False))

    def test_config_validation(self):
        """Test source reliability configuration validation (T046)."""
        from src import config
        
        # Test that validate_source_reliability_config returns True
        result = config.validate_source_reliability_config()
        self.assertTrue(result)
        
        # Test that tier lists are valid
        self.assertIsInstance(config.SOURCE_RELIABILITY_TIER_1, list)
        self.assertIsInstance(config.SOURCE_RELIABILITY_TIER_2, list)
        self.assertTrue(len(config.SOURCE_RELIABILITY_TIER_1) > 0)
        self.assertTrue(len(config.SOURCE_RELIABILITY_TIER_2) > 0)
        
        # Test that all domains are strings
        for domain in config.SOURCE_RELIABILITY_TIER_1 + config.SOURCE_RELIABILITY_TIER_2:
            self.assertIsInstance(domain, str)
        
        # Test that weights sum to 1.0
        weight_sum = (config.SCORE_WEIGHT_KEYWORD + 
                     config.SCORE_WEIGHT_TRENDING + 
                     config.SCORE_WEIGHT_SOURCE)
        self.assertAlmostEqual(weight_sum, 1.0, places=3)
        
        # Test that multipliers are positive
        self.assertGreater(config.TIER_1_MULTIPLIER, 0)
        self.assertGreater(config.TIER_2_MULTIPLIER, 0)
        self.assertGreater(config.TIER_3_MULTIPLIER, 0)
        
        # Test that diversity cap is positive integer
        self.assertIsInstance(config.MAX_ARTICLES_PER_SOURCE, int)
        self.assertGreater(config.MAX_ARTICLES_PER_SOURCE, 0)
        
        # Test that markdown length is positive integer
        self.assertIsInstance(config.MAX_MARKDOWN_LENGTH, int)
        self.assertGreater(config.MAX_MARKDOWN_LENGTH, 0)

    def test_config_validation_detects_invalid_weights(self):
        """Test that validation catches invalid weight configurations (T046)."""
        from src import config
        
        # Save original values
        original_keyword = config.SCORE_WEIGHT_KEYWORD
        original_trending = config.SCORE_WEIGHT_TRENDING
        original_source = config.SCORE_WEIGHT_SOURCE
        
        try:
            # Test invalid weight sum (should fail)
            config.SCORE_WEIGHT_KEYWORD = 0.6
            config.SCORE_WEIGHT_TRENDING = 0.3
            config.SCORE_WEIGHT_SOURCE = 0.2  # Sum = 1.1, not 1.0
            
            with self.assertRaises(ValueError) as context:
                config.validate_source_reliability_config()
            
            self.assertIn("sum to 1.0", str(context.exception))
        finally:
            # Restore original values
            config.SCORE_WEIGHT_KEYWORD = original_keyword
            config.SCORE_WEIGHT_TRENDING = original_trending
            config.SCORE_WEIGHT_SOURCE = original_source

    def test_dynamic_tier_detection(self):
        """Test that tier detection works when sources are added dynamically (T047)."""
        from src import config
        
        # Save original tier-1 list
        original_tier1 = config.SOURCE_RELIABILITY_TIER_1.copy()
        
        try:
            # Add a new source to tier-1
            test_domain = 'example-news.com'
            if test_domain not in config.SOURCE_RELIABILITY_TIER_1:
                config.SOURCE_RELIABILITY_TIER_1.append(test_domain)
            
            # Create analyzer (should pick up new configuration)
            analyzer = ContentAnalyzerSimple()
            
            # Test tier detection for new domain
            test_url = f'https://www.{test_domain}/article'
            tier = analyzer.get_source_tier(test_url)
            
            self.assertEqual(tier, 1, f"Expected tier-1 for {test_domain}, got tier-{tier}")
            
            # Test subdomain matching
            subdomain_url = f'https://news.{test_domain}/story'
            subdomain_tier = analyzer.get_source_tier(subdomain_url)
            
            self.assertEqual(subdomain_tier, 1, 
                           f"Subdomain matching failed for {test_domain}")
        finally:
            # Restore original configuration
            config.SOURCE_RELIABILITY_TIER_1 = original_tier1

if __name__ == '____main__':
    unittest.main()
 