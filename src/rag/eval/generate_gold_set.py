import json
import time

from google import genai

from rag.config.settings import settings

# Facts about a fictional company (for the LLM to generate questions from)
FACTS = [
    "Acme Corp was founded in 1995 by Jane Doe in Seattle.",
    "The company's flagship product is the Acme Rocket, released in 2005.",
    "Acme Rocket generates  million in annual revenue.",
    "In 2010, Acme Corp acquired a smaller competitor called Beta Dynamics for  million.",
    "Acme Corp has 500 employees and offices in Seattle, New York, and London.",
    "The CEO of Acme Corp is John Smith, who took over in 2015.",
    "Acme Corp is publicly traded on the NASDAQ under the ticker ACME.",
    "Acme Corp's main competitor is Globex Corporation.",
    "In 2020, Acme Corp launched a new division focused on AI and machine learning.",
    "Acme Corp's AI division developed the Acme Neural Net, a predictive analytics tool.",
    "The Acme Neural Net is used by 100 enterprise clients.",
    "Acme Corp plans to invest  million in AI research over the next 3 years.",
    "The company's headquarters is a 10-story building in downtown Seattle.",
    "Acme Corp reported a net income of  million in 2022.",
    "The company's stock price rose 25% in 2023.",
    "Acme Corp has a partnership with the University of Washington for AI research.",
    "The Acme Rocket is used by NASA for small satellite launches.",
    "Acme Corp won the 'Best Places to Work' award in 2021.",
    "The company has a 4.5-star rating on Glassdoor.",
    "Acme Corp's customer support is available 24/7 via phone and email."
]

def generate_gold_set():
    print('Generating synthetic gold set using Gemini...')
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    gold_set = []
    for fact in FACTS:
        prompt = f'''Based on this fact, write a single question that can be answered by the fact. 
        Output ONLY the question.
        
        Fact: {fact}'''
        
        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt,
            )
            question = response.text.strip()
            if question:
                gold_set.append({
                    "question": question,
                    "relevant_chunks": [fact]
                })
                print(f'Generated question: {question}')
        except Exception as e:
            print(f'Failed to generate question: {e}')
        
        time.sleep(0.5)  # Rate limit

    with open('eval/gold_set/qa_pairs.json', 'w', encoding='utf-8') as f:
        json.dump(gold_set, f, indent=2)
    print(f'Saved {len(gold_set)} questions to eval/gold_set/qa_pairs.json')

if __name__ == '__main__':
    generate_gold_set()
