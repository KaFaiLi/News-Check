import unittest
import os
from unittest.mock import patch, MagicMock
from src.document_generator import DocumentGenerator

class TestDocumentGenerator(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_output_dir = "test_output"
        os.makedirs(self.test_output_dir, exist_ok=True)
        self.generator = DocumentGenerator(output_dir=self.test_output_dir)
        
        self.test_articles = [
            {
                'article': {
                    'title': 'Test Article 1',
                    'source': 'Test Source',
                    'published_time': '2024-03-01T12:00:00Z',
                    'url': 'http://test1.com',
                    'snippet': 'Test snippet 1'
                },
                'analysis': {
                    'scores': {'AI Development': 0.8, 'Fintech': 0.3, 'GenAI Usage': 0.5},
                    'insights': 'Test insight 1',
                    'overall_score': 0.8
                }
            },
            {
                'article': {
                    'title': 'Test Article 2',
                    'source': 'Test Source 2',
                    'published_time': '2024-03-01T13:00:00Z',
                    'url': 'http://test2.com',
                    'snippet': 'Test snippet 2'
                },
                'analysis': {
                    'scores': {'AI Development': 0.6, 'Fintech': 0.7, 'GenAI Usage': 0.4},
                    'insights': 'Test insight 2',
                    'overall_score': 0.7
                }
            }
        ]

    def tearDown(self):
        """Clean up test files after each test method."""
        for file in os.listdir(self.test_output_dir):
            os.remove(os.path.join(self.test_output_dir, file))
        os.rmdir(self.test_output_dir)

    def test_generate_brief_summary(self):
        """Test brief summary document generation."""
        filepath = self.generator.generate_brief_summary(self.test_articles)
        
        self.assertTrue(os.path.exists(filepath))
        self.assertTrue(filepath.endswith('.docx'))
        self.assertTrue(os.path.getsize(filepath) > 0)

    def test_generate_detailed_report(self):
        """Test detailed report document generation."""
        filepath = self.generator.generate_detailed_report(self.test_articles)
        
        self.assertTrue(os.path.exists(filepath))
        self.assertTrue(filepath.endswith('.docx'))
        self.assertTrue(os.path.getsize(filepath) > 0)

    @patch('langchain_openai.ChatOpenAI')
    def test_generate_overall_summary(self, mock_llm):
        """Test overall summary generation with LLM."""
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = "Test overall summary"
        mock_llm.return_value.invoke.return_value = mock_response
        
        # Create a new generator with mocked LLM
        generator_with_llm = DocumentGenerator(
            output_dir=self.test_output_dir,
            llm_instance=mock_llm.return_value
        )
        
        summary = generator_with_llm._generate_overall_summary(self.test_articles)
        self.assertIsInstance(summary, str)
        self.assertTrue(len(summary) > 0)

    def test_generate_overall_summary_no_llm(self):
        """Test overall summary generation without LLM."""
        summary = self.generator._generate_overall_summary(self.test_articles)
        self.assertIn("LLM not configured", summary)

    def test_empty_articles(self):
        """Test document generation with empty article list."""
        filepath = self.generator.generate_brief_summary([])
        self.assertTrue(os.path.exists(filepath))
        self.assertTrue(filepath.endswith('.docx'))

if __name__ == '__main__':
    unittest.main() 