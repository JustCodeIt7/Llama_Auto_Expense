import pandas as pd
import os
import json
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from rich import print

# --- Configuration Constants ---
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://eos-parkmour.netbird.cloud:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:27b")
DATA_DIR = "data"
INPUT_EXCEL_PATH = os.path.join(DATA_DIR, "Retail.OrderHistory.1.xlsx")
OUTPUT_CSV_PATH = os.path.join(DATA_DIR, "categorized_expenses.csv")

# Tax categorization prompt template
EXPENSE_CATEGORIZATION_PROMPT = """
    You are an AI assistant specialized in US tax law for Limited Liability Companies (LLCs).
    Your task is to analyze potential business expenses, categorize them, and determine their likely tax deductibility.
    **Context:**
    The expense details below are for a US-based LLC. Assume the expense was incurred with a potential business purpose unless contradicted by the product name.
    An expense is generally tax-deductible for an LLC if it is both **ordinary** (common and accepted in the trade or business) and **necessary** (helpful and appropriate for the trade or business).
    **Expense Details:**
    - Product Name: {product_name}
    - Unit Price: {unit_price}
    - Quantity: {quantity}
    - Order Date: {order_date}
    **Instructions:**
    1.  **Categorize** the expense into one of the following common business categories:
        * Office Supplies & Software
        * Computer Hardware & Equipment
        * Professional Development & Education
        * Marketing & Advertising
        * Travel & Meals (Specify which)
        * Utilities
        * Rent & Lease
        * Subscriptions & Dues
        * Cost of Goods Sold (COGS) - if the item is clearly for resale or direct use in producing income
        * Repairs & Maintenance
        * Insurance
        * Professional Services (Legal, Accounting)
        * Other Business Expense
        * Potentially Personal / Non-Deductible
    2.  Determine if the expense is **likely tax-deductible** for the LLC (true/false). Consider the "ordinary and necessary" rule. If it seems personal, mark as false.
    3.  Provide a brief **justification** explaining your reasoning for the category and deductibility assessment.
    **Output Format:**
    Return your response ONLY as a valid JSON object with the following keys:
    - "category": string (The determined expense category)
    - "is_deductible": boolean (true or false)
    - "justification": string (Your brief reasoning)
    **Example Input Expense:**
    Product Name: Subscription to Adobe Creative Cloud
    Unit Price: 59.99
    Quantity: 1
    Order Date: 2024-01-15
    **Example JSON Output:**
    ```json
    {{
      "category": "Office Supplies & Software",
      "is_deductible": true,
      "justification": "Software subscription like Adobe Creative Cloud is ordinary and necessary for businesses involved in design, marketing, or content creation."
    }}
    ```
    **Analyze the expense provided above and return the JSON output.**
    """


def setup_directories():
    """Ensure necessary directories exist."""
    os.makedirs(DATA_DIR, exist_ok=True)


def import_llm_module():
    """Import the appropriate ChatOllama module."""
    try:
        from langchain_ollama import ChatOllama

        print("Successfully imported ChatOllama from langchain_ollama.")
        return ChatOllama
    except ImportError:
        try:
            from langchain_community.chat_models import ChatOllama

            print("Imported ChatOllama from langchain_community.chat_models.")
            print("Note: Consider updating Langchain packages for latest features.")
            return ChatOllama
        except ImportError:
            print("Error: Could not import ChatOllama.")
            print("Please install required packages: pip install pandas openpyxl langchain langchain-community langchain-ollama")
            exit(1)


def initialize_llm(ChatOllama):
    """Initialize the LLM with appropriate settings."""
    try:
        llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, format="json", temperature=0.3)
        print(f"Initialized ChatOllama with model '{OLLAMA_MODEL}' at {OLLAMA_BASE_URL}")
        return llm
    except Exception as e:
        print(f"Error initializing ChatOllama: {e}")
        print(f"Please ensure Ollama server is running at {OLLAMA_BASE_URL} and model '{OLLAMA_MODEL}' is available.")
        exit(1)


def create_processing_chain(llm):
    """Create the Langchain processing chain with prompt template and JSON output parsing."""
    prompt_template = ChatPromptTemplate.from_template(EXPENSE_CATEGORIZATION_PROMPT)
    return prompt_template | llm | JsonOutputParser()


def safe_json_loads(json_string):
    """Safely parses a JSON string, returning None on failure."""
    try:
        if json_string.strip().startswith("```json"):
            json_string = json_string.strip()[7:-3].strip()
        elif json_string.strip().startswith("```"):
            json_string = json_string.strip()[3:-3].strip()
        return json.loads(json_string)
    except json.JSONDecodeError:
        print(f"Warning: Failed to decode JSON: {json_string}")
        return None
    except Exception as e:
        print(f"Warning: An unexpected error occurred during JSON parsing: {e}")
        return None


def process_expenses(input_path, output_path, processing_chain):
    """
    Reads expenses from an Excel file, categorizes them using LLM,
    and saves the results to a CSV file.
    """
    print("Starting expense processing...")
    print(f"Reading input Excel file: {input_path}")

    try:
        df = pd.read_excel(input_path)
        print(f"Successfully read {len(df)} rows from {input_path}")
    except FileNotFoundError:
        print(f"Error: Input file not found at {input_path}")
        return
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return

    # Prepare lists to store results
    categories = []
    deductibility = []
    justifications = []

    # Iterate through each expense row
    for index, row in df.iterrows():
        print(f"\nProcessing row {index + 1}/{len(df)}...")

        # Extract relevant data for the prompt
        product_name = row.get("Product Name", "N/A")
        unit_price = row.get("Unit Price", 0.0)
        quantity = row.get("Quantity", 1)
        order_date = row.get("Order Date", "N/A")

        # Skip rows with missing essential data
        if product_name == "N/A":
            print(f"Skipping row {index + 1} due to missing 'Product Name'.")
            categories.append("Unknown")
            deductibility.append(False)
            justifications.append("Missing product information")
            continue

        try:
            # Process the expense through the LLM chain
            result = processing_chain.invoke(
                {"product_name": product_name, "unit_price": unit_price, "quantity": quantity, "order_date": order_date}
            )

            # Store the results
            categories.append(result.get("category", "Unknown"))
            deductibility.append(result.get("is_deductible", False))
            justifications.append(result.get("justification", "No justification provided"))

            print(f"Product: {product_name}")
            print(f"Categorized as: {result.get('category', 'Unknown')}")
            print(f"Deductible: {result.get('is_deductible', False)}")

        except Exception as e:
            print(f"Error processing row {index + 1}: {e}")
            categories.append("Error")
            deductibility.append(False)
            justifications.append(f"Processing error: {str(e)}")

    # Add the analysis results to the dataframe
    df["Category"] = categories
    df["Is Deductible"] = deductibility
    df["Justification"] = justifications

    # Save the results
    print(f"\nSaving results to {output_path}")
    df.to_csv(output_path, index=False)
    print(f"Processing complete. Results saved to {output_path}")


def main():
    # Setup environment
    setup_directories()

    # Initialize language model
    ChatOllama = import_llm_module()
    llm = initialize_llm(ChatOllama)

    # Create processing chain
    processing_chain = create_processing_chain(llm)

    # Process expenses
    process_expenses(INPUT_EXCEL_PATH, OUTPUT_CSV_PATH, processing_chain)


if __name__ == "__main__":
    main()
