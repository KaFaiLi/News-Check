# News-Check

A Python-based news aggregation and analysis tool that fetches, analyzes, and summarizes news articles from various sources.

## Features

- **News Aggregation**: Fetches news articles from multiple sources using Google News search
- **Content Analysis**: Analyzes article content using keyword matching and LLM-based insights
- **Trending Analysis**: Identifies trending topics and calculates article relevance scores
- **Category-based Filtering**: Organizes articles into categories (AI Development, Fintech, GenAI Usage)
- **Minimum Category Requirements**: Ensures minimum representation of Fintech articles (at least 3) in top results
- **Smart Content Extraction**: Handles paywalled content and extracts meaningful article content
- **Automated Summaries**: Generates both brief and detailed summaries of news articles
- **Email-ready Output**: Creates formatted HTML content ready for email distribution

## Requirements

- Python 3.8+
- Required Python packages (see `requirements.txt`):
  - pandas
  - python-docx
  - beautifulsoup4
  - requests
  - fuzzywuzzy
  - langchain
  - langchain-openai
  - playwright
  - html2text

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/News-Check.git
cd News-Check
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install
```

4. Set up environment variables:
Create a `.env` file with your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

## Usage

1. Run the main script:
```bash
python main.py
```

2. The script will:
   - Fetch recent news articles
   - Analyze and categorize them
   - Ensure minimum Fintech article representation
   - Generate summaries and reports
   - Create email-ready content

3. Output files will be created in the `Output` directory:
   - `brief_news_summary_[timestamp].docx`: Concise summary of top articles
   - `detailed_news_report_[timestamp].docx`: Detailed analysis of all articles
   - `email_content_[timestamp].html`: Formatted HTML for email distribution
   - `news_articles.xlsx`: Raw article data

## Configuration

The script can be configured by modifying the following parameters in `src/config.py`:

- `OPENAI_API_KEY`: Your OpenAI API key
- `OPENAI_API_BASE`: Base URL for OpenAI API (if using a different provider)
- `USE_LLM`: Enable/disable LLM-based analysis
- `LLM_THRESHOLD`: Score threshold for LLM analysis
- `OUTPUT_DIR`: Directory for output files

## Article Categories

Articles are categorized into:
- **AI Development**: Articles about AI research, neural networks, and technical developments
- **Fintech**: Articles about financial technology, digital banking, and payment systems
- **GenAI Usage**: Articles about generative AI applications and implementations
- **Other**: Articles that don't fit into the above categories

## Minimum Category Requirements

The system ensures that at least 3 Fintech articles are included in the top results. If fewer than 3 Fintech articles are found in the initial top results:
1. The system will look for additional Fintech articles in the remaining pool
2. Lower-scoring non-Fintech articles will be replaced with higher-scoring Fintech articles
3. If insufficient Fintech articles are available, a warning will be displayed

## Error Handling

The system includes robust error handling for:
- Network issues
- Paywalled content
- Invalid URLs
- Content extraction failures
- API rate limits

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Directory Structure

```
News-Check/
├── main.py                        # Main entry point
├── src/
│   ├── __init__.py               # Package initialization
│   ├── news_scraper_simple.py    # News scraping module
│   ├── content_analyzer_simple.py # Content analysis module
│   ├── document_generator.py      # Document generation module
│   ├── config.py                 # Configuration settings
│   └── models.py                 # Data models
├── Output/                       # Generated reports
└── requirements.txt              # Project dependencies
```

## Acknowledgments

- Google News for providing news data
- OpenAI for language model support
- Various open-source libraries used in this project
