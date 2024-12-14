import os
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from docx import Document
import pdfplumber
import json
import time

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = "http://3.83.24.72:8000/"  # Replace with the actual base URL

# Initialize LangChain OpenAI model
llm = ChatOpenAI(model="gpt-4", openai_api_key=OPENAI_API_KEY, temperature=0.2)


# Function to parse BRD
def parse_brd(file_path):
    if file_path.endswith('.docx'):
        # Extract text from .docx file
        document = Document(file_path)
        content = "\n".join([para.text for para in document.paragraphs])
    elif file_path.endswith('.pdf'):
        # Extract text from .pdf file
        content = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                content += page.extract_text() + "\n"
    else:
        raise ValueError("Unsupported file format. Use .docx or .pdf files.")

    # Use LangChain to extract features and requirements
    system_template = "You are a testing expert. Extract features and test cases from the given BRD document text."
    human_template = "Document content:\n{content}\n\nExtract and format the output as JSON with 'features' and 'test_cases'."

    system_message = SystemMessagePromptTemplate.from_template(system_template)
    human_message = HumanMessagePromptTemplate.from_template(human_template)
    chat_prompt = ChatPromptTemplate.from_messages([system_message, human_message])

    prompt = chat_prompt.format(content=content)
    response = llm.predict(prompt)
    print(response)
    return json.loads(response)


# Function to perform automated testing with Selenium
def perform_tests(base_url, test_cases):
    # Setup Selenium WebDriver
    chrome_options = Options()
    # chrome_options.add_argument()  # Run in headless mode for automation
    driver = webdriver.Chrome(service=Service(), options=chrome_options)
    driver.get(base_url)

    results = []

    for case in test_cases:
        try:
            feature = case["feature"]
            actions = case["actions"]

            for action in actions:
                element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, action["xpath"]))
                )

                if action["type"] == "click":
                    element.click()
                elif action["type"] == "input":
                    element.send_keys(action["value"])
                elif action["type"] == "hover":
                    ActionChains(driver).move_to_element(element).perform()

                time.sleep(1)  # Add delay for visual inspection during testing

            results.append({"feature": feature, "status": "Pass", "details": "Executed successfully"})
        except Exception as e:
            results.append({"feature": feature, "status": "Fail", "details": str(e)})

    driver.quit()
    return results


# Function to generate a final report
def generate_report(results):
    report = {
        "summary": {
            "total_tests": len(results),
            "passed": len([r for r in results if r["status"] == "Pass"]),
            "failed": len([r for r in results if r["status"] == "Fail"]),
        },
        "details": results,
    }

    report_path = "test_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=4)

    print(f"Test report generated: {report_path}")


# Main function to run the testing pipeline
def run_tests(brd_file, base_url):
    # Step 1: Parse BRD and extract test cases
    print("Parsing BRD and extracting test cases...")
    requirements = parse_brd(brd_file)
    test_cases = requirements["test_cases"]

    # Step 2: Perform tests with Selenium
    print("Performing tests on the webpage...")
    results = perform_tests(base_url, test_cases)

    # Step 3: Generate a final report
    print("Generating final test report...")
    generate_report(results)


# Example usage
if __name__ == "__main__":
    brd_file = "BRD - HRMS.pdf"  # Replace with your BRD file path
    base_url = BASE_URL  # Replace with your web application URL
    run_tests(brd_file, base_url)
