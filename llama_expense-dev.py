# ============================================================
# TAX EXPENSE CATEGORIZER - YAML VERSION
# ============================================================
# This script categorizes business expenses using LLMs for tax purposes
import pandas as pd
import os
import json
from rich import print
from langchain_core.output_parsers import JsonOutputParser
from langchain_ollama import ChatOllama
from dotenv import load_dotenv
import time
from langchain_core.prompts import load_prompt

load_dotenv(".env")


# ============================================================
# 1. CONFIGURATION SECTION
# ============================================================
# File paths
DATA_DIR = "data"
INPUT_EXCEL_PATH = os.path.join(DATA_DIR, "test_input.csv")
OUTPUT_CSV_PATH = os.path.join(DATA_DIR, "categorized_expenses.csv")
PROMPT_FILE_PATH = "prompt.yaml"

# Default values
DEFAULT_CATEGORY = "Unknown"
DEFAULT_DEDUCTIBLE = False
ERROR_CATEGORY = "Error"
DEFAULT_JUSTIFICATION = "No justification provided by LLM"
DATE_FORMAT = "%Y-%m-%d"

# LLM Configuration
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
# OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
# OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral")
# OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi4-mini")
# OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi4")
# OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:12b")


# ============================================================
# 2. PROMPT LOADING FUNCTION
# ============================================================
def load_prompt_from_file(file_path):
    """Loads the prompt from a YAML file."""
    try:
        prompt = load_prompt(file_path)
        print(f"✓ Successfully loaded prompt from {file_path}")
        return prompt
    except FileNotFoundError:
        print(f"❌ Error: Prompt file not found at {file_path}")
        print("Please ensure 'prompt.yaml' exists in the directory.")
        exit(1)
    except Exception as e:
        print(f"❌ Error loading prompt: {e}")
        exit(1)


# ============================================================
# 3. UTILITY FUNCTIONS
# ============================================================
def setup_directories():
    """Ensure necessary directories exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"✓ Ensured data directory exists: {DATA_DIR}")


def parse_date(date_value):
    """Parse date value to a consistent format. Will raise error on failure."""
    if isinstance(date_value, pd.Timestamp):
        return date_value.strftime(DATE_FORMAT)
    else:
        # This will raise ValueError or other exceptions if parsing fails
        return pd.to_datetime(date_value).strftime(DATE_FORMAT)


def direct_json_loads(json_string):
    """Directly parses a JSON string, raising errors on failure."""
    # Handle potential markdown code blocks around JSON
    if isinstance(json_string, str):
        if json_string.strip().startswith("```json"):
            json_string = json_string.strip()[7:-3].strip()
        elif json_string.strip().startswith("```"):
            json_string = json_string.strip()[3:-3].strip()
    # If it's already a dict (parsed by JsonOutputParser), return it directly
    if isinstance(json_string, dict):
        return json_string
    # This will raise json.JSONDecodeError if parsing fails
    return json.loads(json_string)


# ============================================================
# 4. DATA HANDLING FUNCTIONS
# ============================================================
def read_expense_data(input_path):
    """Read expense data from CSV file. Will raise error on failure."""
    # This will raise FileNotFoundError or other pandas errors if issues occur
    df = pd.read_csv(input_path)
    print(f"✓ Successfully read {len(df)} rows from {input_path}")
    return df


def save_expense_data(df, output_path):
    """Save processed expense data to CSV file."""
    df.to_csv(output_path, index=False)
    print(f"✓ Processing complete. Results saved to {output_path}")
    return True


# ============================================================
# 5. LLM SETUP FUNCTIONS
# ============================================================
def initialize_llm(ChatOllama):
    """Initialize the LLM with appropriate settings."""
    llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, format="json", temperature=0.2, seeds=42)
    print(f"✓ Initialized ChatOllama with model '{OLLAMA_MODEL}' at {OLLAMA_BASE_URL}")
    return llm


# Modified to use the langchain prompt object directly
def create_processing_chain(llm, prompt):
    """Create the Langchain processing chain with prompt template and JSON output parsing."""
    if not prompt:
        print("❌ Error: Prompt is empty. Cannot create processing chain.")
        exit(1)

    chain = prompt | llm | JsonOutputParser()
    print("✓ Created LLM processing chain with prompt template and JSON parser")
    return chain


# ============================================================
# 6. EXPENSE PROCESSING FUNCTIONS
# ============================================================
def process_single_expense(row, processing_chain, index, total_rows):
    """
    Process a single expense row using the LLM chain.
    Will raise errors if LLM call or JSON parsing fails.
    """
    # Extract relevant data for the prompt
    product_name = row.get("Product Name", "N/A")
    unit_price = row.get("Unit Price", 0.0)
    quantity = row.get("Quantity", 1)
    order_date = parse_date(row.get("Order Date", "N/A"))

    # Skip rows with missing essential data
    if product_name == "N/A":
        print(f"⚠️ Skipping row {index + 1} due to missing 'Product Name'.")
        # Returning defaults here as skipping isn't an error condition
        return DEFAULT_CATEGORY, DEFAULT_DEDUCTIBLE, "Missing product information"

    # Process the expense through the LLM chain - This will raise an error if the LLM call fails
    result_raw = processing_chain.invoke(
        {
            "product_name": product_name,
            "unit_price": unit_price,
            "quantity": quantity,
            "order_date": order_date,
        }
    )

    # Directly parse the JSON output
    result = direct_json_loads(result_raw)

    # If parsing succeeds (no error raised), extract data
    category = result.get("category", DEFAULT_CATEGORY)
    is_deductible = result.get("is_deductible", DEFAULT_DEDUCTIBLE)
    justification = result.get("justification", DEFAULT_JUSTIFICATION)

    # Log results
    print(f"  📦 Product: {product_name}")
    print(f"  🏷️ Categorized as: {category}")
    print(f"  💰 Deductible: {is_deductible}")
    print(f"  📝 Justification: {justification}")

    return category, is_deductible, justification


def process_expenses(input_path, output_path, processing_chain):
    """
    Reads expenses from a CSV file, categorizes them using LLM,
    adds justification, and saves the results to a new CSV file.
    Will halt on the first error encountered during processing.
    """
    print("\n🚀 Starting expense processing...")
    print(f"📂 Reading input CSV file: {input_path}")

    # Read the input data - will raise error if file not found or invalid
    df = read_expense_data(input_path)

    # Prepare lists to store results
    categories = []
    deductibility = []
    justifications = []

    # Process each expense row
    # This loop will stop if process_single_expense raises an error
    for index, row in df.iterrows():
        print(f"\n⏳ Processing row {index + 1}/{len(df)}...")
        try:
            category, is_deductible, justification = process_single_expense(row, processing_chain, index, len(df))
        except Exception as e:
            # Log the error and provide default error values for this row
            print(f"❌ Error processing row {index + 1}: {e}")
            print("   Assigning error values and continuing to the next row.")
            category = ERROR_CATEGORY
            is_deductible = DEFAULT_DEDUCTIBLE
            justification = f"Error during processing: {e}"
            # Depending on requirements, you might want to re-raise the exception or exit the script here instead of continuing.
            # raise e  # Uncomment to re-raise the exception
            # exit(1) # Uncomment to stop on first error

        categories.append(category)
        deductibility.append(is_deductible)
        justifications.append(justification)

    # Add the analysis results to the dataframe
    df["Category"] = categories
    df["Is Deductible"] = deductibility
    df["Justification"] = justifications

    # Save the results
    print(f"\n💾 Saving results to {output_path}")
    save_expense_data(df, output_path)


# ============================================================
# 7. MAIN FUNCTION
# ============================================================
def main():
    """Main function to run the expense categorization process."""
    start_time = time.time()
    print("\n==== TAX EXPENSE CATEGORIZER (YAML EDITION) ====")

    # Step 1: Setup environment
    setup_directories()

    # Step 2: Load the prompt from the YAML file
    expense_categorization_prompt = load_prompt_from_file(PROMPT_FILE_PATH)

    # Step 3: Initialize language model
    llm = initialize_llm(ChatOllama)

    # Step 4: Create processing chain using the loaded prompt object
    processing_chain = create_processing_chain(llm, expense_categorization_prompt)

    # Step 5: Process expenses - Script will handle errors per row
    process_expenses(INPUT_EXCEL_PATH, OUTPUT_CSV_PATH, processing_chain)

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"\nExecution time: {elapsed_time:.2f} seconds")
    print("\n✅ Process completed!")


if __name__ == "__main__":
    main()
