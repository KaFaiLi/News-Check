# News-Check

A Python-based news scraping and analysis tool that fetches, analyzes, and summarizes news articles related to AI, Fintech, and Technology using Google News RSS feeds and OpenAI's language models.

## Features

- **News Scraping**: Fetches articles from Google News RSS feeds with customizable keywords and date ranges
- **Content Analysis**: 
  - Analyzes article relevance using keyword matching and fuzzy string comparison
  - Categorizes articles into AI Development, Fintech, and GenAI Usage
  - Generates insights using OpenAI's language models
- **Document Generation**:
  - Creates brief summaries (top 3 articles)
  - Generates detailed reports (top 10 articles)
  - Includes category distribution and trend analysis
- **Duplicate Detection**: Removes similar articles using fuzzy matching
- **Error Handling**: Implements robust error handling and retry mechanisms

## Directory Structure

```
News-Check/
├── src/
│   ├── news_scraper_simple.py     # Main script
│   ├── content_analyzer_simple.py  # Content analysis module
│   ├── document_generator.py       # Document generation module
│   ├── config.py                  # Configuration settings
│   └── models.py                  # Data models
├── tests/                         # Test files
├── docs/                          # Documentation
├── Output/                        # Generated reports
└── requirements.txt               # Project dependencies
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/News-Check.git
cd News-Check
```

2. Create and activate a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure API settings:
- Open `src/config.py`
- Set your OpenAI API key and base URL
- Adjust other settings as needed

## Usage

1. Run the news scraper:
```bash
python src/news_scraper_simple.py
```

2. The script will:
- Fetch news articles from the last 14 days
- Analyze content and relevance
- Generate two Word documents in the `Output` directory:
  - `brief_summary.docx`: Top 3 most relevant articles
  - `detailed_report.docx`: Detailed analysis of top 10 articles

## Configuration

Key settings in `src/config.py`:
- `OPENAI_API_KEY`: Your OpenAI API key
- `OPENAI_API_BASE`: API base URL
- `LLM_THRESHOLD`: Minimum relevance score for LLM analysis
- `MAX_ARTICLES`: Maximum articles to fetch per keyword
- `REQUEST_TIMEOUT`: Request timeout in seconds

## Dependencies

Main dependencies include:
- `feedparser`: RSS feed parsing
- `pandas`: Data manipulation
- `langchain`: LLM integration
- `python-docx`: Word document generation
- `fuzzywuzzy`: String matching
- `requests`: HTTP requests

## Testing

Run tests using:
```bash
python -m pytest tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Google News RSS feeds for providing news data
- OpenAI for language model support
- Various open-source libraries used in this project
