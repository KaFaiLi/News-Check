import re

class SimpleKeywordMatcher:
    def __init__(self):
        # Keywords for relevant categories
        self.ai_development_keywords = [
            'artificial intelligence development', 'ai research', 'neural network',
            'machine learning algorithm', 'deep learning', 'ai model', 'transformer',
            'computer vision', 'natural language processing', 'nlp', 'ai advancement',
            'ai breakthrough', 'ai innovation', 'large language model', 'llm'
        ]
        
        self.fintech_keywords = [
            'financial technology', 'fintech', 'digital banking', 'cryptocurrency',
            'blockchain', 'digital payment', 'regtech', 'insurtech', 'open banking',
            'roboadvisor', 'digital wallet', 'payment processing', 'financial software',
            'financial service platform', 'banking technology', 'finance automation'
        ]
        
        self.genai_usage_keywords = [
            'generative ai', 'gpt', 'chatgpt', 'dall-e', 'midjourney', 'stable diffusion',
            'ai content generation', 'ai writing', 'ai art', 'ai image', 'ai video',
            'ai music', 'text-to-image', 'text-to-video', 'ai assistant', 'ai productivity',
            'ai tool', 'ai application', 'ai implementation', 'ai adoption', 'ai integration'
        ]
        
        # Compile regexes for faster matching
        self.ai_regex = self._compile_keyword_regex(self.ai_development_keywords)
        self.fintech_regex = self._compile_keyword_regex(self.fintech_keywords)
        self.genai_regex = self._compile_keyword_regex(self.genai_usage_keywords)

    def _compile_keyword_regex(self, keywords):
        """Compile keywords into a single regex pattern for efficient searching"""
        escaped_keywords = [re.escape(kw) for kw in keywords]
        pattern = r'\b(' + '|'.join(escaped_keywords) + r')\b'
        return re.compile(pattern, re.IGNORECASE)

    def keyword_relevance_score(self, text):
        """Calculate relevance scores based on keyword matching"""
        # Normalize text for consistent matching
        text = text.lower()
        text_length = len(text.split())
        
        # Count matches for each category
        ai_matches = len(re.findall(self.ai_regex, text))
        fintech_matches = len(re.findall(self.fintech_regex, text))
        genai_matches = len(re.findall(self.genai_regex, text))
        
        # Calculate density scores (matches per word, scaled)
        ai_score = min(ai_matches / max(text_length/20, 1), 1.0)
        fintech_score = min(fintech_matches / max(text_length/20, 1), 1.0)
        genai_score = min(genai_matches / max(text_length/20, 1), 1.0)
        
        # Overall relevance = max of individual scores, with bonus for multiple categories
        combined_score = max(ai_score, fintech_score, genai_score)
        multi_category_bonus = min((ai_score + fintech_score + genai_score) / 3, 0.3)
        overall_score = min(combined_score + multi_category_bonus, 1.0)
        
        primary_category = self._determine_primary_category(ai_score, fintech_score, genai_score)
        
        return {
            'ai_development': ai_score,
            'fintech': fintech_score,
            'genai_usage': genai_score,
            'overall': overall_score,
            'primary_category': primary_category
        }
    
    def _determine_primary_category(self, ai_score, fintech_score, genai_score):
        """Determine the primary category based on scores"""
        scores = {
            'AI Development': ai_score,
            'Fintech': fintech_score,
            'GenAI Usage': genai_score
        }
        if max(scores.values()) < 0.1:
            return 'Other'
        return max(scores, key=scores.get)


def run_test():
    matcher = SimpleKeywordMatcher()
    
    # Test some sample texts
    test_texts = [
        "New research in artificial intelligence development shows promising results in natural language processing",
        "Digital banking platforms are revolutionizing how financial technology is deployed in emerging markets",
        "ChatGPT and other generative AI tools are being integrated into business workflows",
        "Fintech companies are leveraging generative AI for financial forecasting and fraud detection",
        "Tech company releases new smartphone with improved camera",  # Should be "Other"
        "GPT-4 is being used by banks to improve fraud detection systems"  # Mixed GenAI and Fintech
    ]
    
    print("Testing keyword matching functionality")
    print("=====================================\n")
    
    for i, text in enumerate(test_texts):
        scores = matcher.keyword_relevance_score(text)
        print(f"Text {i+1}: {text}")
        print(f"  AI Development: {scores['ai_development']:.2f}")
        print(f"  Fintech: {scores['fintech']:.2f}")
        print(f"  GenAI Usage: {scores['genai_usage']:.2f}")
        print(f"  Overall: {scores['overall']:.2f}")
        print(f"  Primary Category: {scores['primary_category']}")
        print()
    
    # Test a real article
    print("\nTesting with a real article")
    print("===========================\n")
    
    article_title = "How Banks Are Using ChatGPT to Improve Customer Service"
    article_snippet = "Major financial institutions are implementing generative AI tools to enhance customer interactions and streamline operations. The technology is showing promising results in fraud detection and personalized financial advice."
    
    full_text = f"{article_title} {article_snippet}"
    scores = matcher.keyword_relevance_score(full_text)
    
    print(f"Article: {article_title}")
    print(f"Snippet: {article_snippet}")
    print(f"Analysis results:")
    print(f"  AI Development: {scores['ai_development']:.2f}")
    print(f"  Fintech: {scores['fintech']:.2f}")
    print(f"  GenAI Usage: {scores['genai_usage']:.2f}")
    print(f"  Overall: {scores['overall']:.2f}")
    print(f"  Primary Category: {scores['primary_category']}")
    

if __name__ == "__main__":
    run_test() 