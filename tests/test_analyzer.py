from content_analyzer import ContentAnalyzer

def test_keyword_matching():
    """Test if keyword matching is working correctly"""
    analyzer = ContentAnalyzer()
    
    # Test some sample texts
    ai_text = "New research in artificial intelligence development shows promising results in natural language processing"
    fintech_text = "Digital banking platforms are revolutionizing how financial technology is deployed in emerging markets"
    genai_text = "ChatGPT and other generative AI tools are being integrated into business workflows"
    mixed_text = "Fintech companies are leveraging generative AI for financial forecasting and fraud detection"
    
    print("Testing keyword matching functionality:")
    print("-------------------------------------")
    
    print("\nAI Development Text:")
    ai_scores = analyzer.keyword_relevance_score(ai_text)
    print(f"  AI Development score: {ai_scores['ai_development']:.2f}")
    print(f"  Fintech score: {ai_scores['fintech']:.2f}")
    print(f"  GenAI Usage score: {ai_scores['genai_usage']:.2f}")
    print(f"  Overall score: {ai_scores['overall']:.2f}")
    print(f"  Primary category: {ai_scores['primary_category']}")
    
    print("\nFintech Text:")
    fintech_scores = analyzer.keyword_relevance_score(fintech_text)
    print(f"  AI Development score: {fintech_scores['ai_development']:.2f}")
    print(f"  Fintech score: {fintech_scores['fintech']:.2f}")
    print(f"  GenAI Usage score: {fintech_scores['genai_usage']:.2f}")
    print(f"  Overall score: {fintech_scores['overall']:.2f}")
    print(f"  Primary category: {fintech_scores['primary_category']}")
    
    print("\nGenAI Text:")
    genai_scores = analyzer.keyword_relevance_score(genai_text)
    print(f"  AI Development score: {genai_scores['ai_development']:.2f}")
    print(f"  Fintech score: {genai_scores['fintech']:.2f}")
    print(f"  GenAI Usage score: {genai_scores['genai_usage']:.2f}")
    print(f"  Overall score: {genai_scores['overall']:.2f}")
    print(f"  Primary category: {genai_scores['primary_category']}")
    
    print("\nMixed Text:")
    mixed_scores = analyzer.keyword_relevance_score(mixed_text)
    print(f"  AI Development score: {mixed_scores['ai_development']:.2f}")
    print(f"  Fintech score: {mixed_scores['fintech']:.2f}")
    print(f"  GenAI Usage score: {mixed_scores['genai_usage']:.2f}")
    print(f"  Overall score: {mixed_scores['overall']:.2f}")
    print(f"  Primary category: {mixed_scores['primary_category']}")

def test_analyze_article():
    """Test if article analysis works with mock data"""
    analyzer = ContentAnalyzer()
    
    # Create a mock article
    article = {
        "title": "How Banks Are Using ChatGPT to Improve Customer Service",
        "snippet": "Major financial institutions are implementing generative AI tools to enhance customer interactions and streamline operations. The technology is showing promising results in fraud detection and personalized financial advice.",
        "source": "Financial Times",
        "published_time": "2023-06-15T14:30:00"
    }
    
    print("\n\nTesting article analysis functionality:")
    print("-------------------------------------")
    
    # Test full article analysis
    analysis = analyzer.analyze_article(article)
    
    print(f"\nArticle Title: {article['title']}")
    print(f"Analysis results:")
    print(f"  Relevance Score: {analysis['relevance_score']:.2f}")
    print(f"  Category: {analysis['category']}")
    print(f"  Impact Level: {analysis['impact_level']}")
    print(f"  Key Points: {analysis['key_points']}")

if __name__ == "__main__":
    test_keyword_matching()
    test_analyze_article() 