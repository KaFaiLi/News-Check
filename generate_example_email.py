import os
from src.document_generator import DocumentGenerator
from datetime import datetime

# Define sample article data (similar to test data)
sample_articles = [
    {
        'article': {
            'title': 'Revolutionizing Finance: How AI is Shaping the Future of Banking',
            'source': 'FinTech Today',
            'published_time': '2024-07-28T09:30:00Z',
            'url': 'http://example.com/ai-in-banking',
            'snippet': 'AI algorithms are increasingly used for fraud detection, customer service, and personalized banking experiences.'
        },
        'analysis': {
            'scores': {'AI Development': 0.9, 'Fintech': 0.85, 'GenAI Usage': 0.7},
            'insights': [
                'Significant advancements in AI-driven fraud detection systems.',
                'Banks are leveraging AI chatbots for 24/7 customer support.',
                'Personalized financial advice through AI is becoming more common.'
            ],
            'overall_score': 0.88
        }
    },
    {
        'article': {
            'title': 'The Rise of Generative AI in Content Creation for Financial Services',
            'source': 'AI Innovations Weekly',
            'published_time': '2024-07-27T14:15:00Z',
            'url': 'http://example.com/genai-finance-content',
            'snippet': 'Generative AI tools are helping financial institutions create marketing materials, reports, and customer communications more efficiently.'
        },
        'analysis': {
            'scores': {'AI Development': 0.75, 'Fintech': 0.6, 'GenAI Usage': 0.9},
            'insights': 'Generative AI is streamlining content workflows, but ensuring accuracy and compliance remains a key challenge. • Ethical considerations for AI-generated financial advice are paramount.',
            'overall_score': 0.78
        }
    },
    {
        'article': {
            'title': 'Navigating the Regulatory Landscape for AI in FinTech',
            'source': 'Regulatory Review',
            'published_time': '2024-07-29T11:00:00Z',
            'url': 'http://example.com/ai-fintech-regulation',
            'snippet': 'Regulators are closely examining the use of AI in financial services to address risks and ensure consumer protection.'
        },
        'analysis': {
            'scores': {'AI Development': 0.6, 'Fintech': 0.9, 'GenAI Usage': 0.5},
            'insights': 'Developing a clear regulatory framework is crucial for fostering innovation while mitigating risks. • Transparency and explainability of AI models are key focus areas for regulators.',
            'overall_score': 0.82
        }
    },
    { # Add a fourth article to test the 'top 3' logic
        'article': {
            'title': 'Cybersecurity in the Age of AI-Powered Financial Systems',
            'source': 'Secure Finance Hub',
            'published_time': '2024-07-28T16:45:00Z',
            'url': 'http://example.com/ai-cybersecurity-finance',
            'snippet': 'AI is a double-edged sword in cybersecurity, offering advanced threat detection but also creating new vulnerabilities if not managed properly.'
        },
        'analysis': {
            'scores': {'AI Development': 0.8, 'Fintech': 0.7, 'GenAI Usage': 0.65},
            'insights': 'AI-driven anomaly detection is enhancing security. • Concerns exist about AI-powered attacks.',
            'overall_score': 0.75
        }
    }
]

# Define the output directory
output_directory = "generated_examples"
os.makedirs(output_directory, exist_ok=True)

# Create an instance of DocumentGenerator
# No LLM instance is provided, so the overall summary in brief reports will be the placeholder.
# For email, the LLM-based overall summary is not part of the redesigned template.
generator = DocumentGenerator(output_dir=output_directory)

if __name__ == "__main__":
    print(f"Generating example email content...")
    try:
        html_output_path = generator.generate_email_content(sample_articles)
        # The generate_email_content now returns the HTML string,
        # and the filename is constructed inside it.
        # We need to find the saved file or rely on the internal saving.
        
        # Let's find the latest HTML file in the output_directory as the method saves it
        list_of_files = [os.path.join(output_directory, f) for f in os.listdir(output_directory) if f.startswith("email_content_") and f.endswith(".html")]
        if not list_of_files:
            print("Error: HTML file was not found in the output directory.")
        else:
            latest_file = max(list_of_files, key=os.path.getctime)
            print(f"Successfully generated example email HTML!")
            print(f"File saved at: {os.path.abspath(latest_file)}")
            print("You can open this file in a web browser to view the email.")

    except Exception as e:
        print(f"An error occurred: {e}") 