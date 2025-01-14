from dataclasses import asdict, dataclass
import json
import re
from typing import Optional
import pdfplumber

@dataclass
class Module:
    module_id: str
    title: str
    level: Optional[str] = None
    language: Optional[str] = None
    semester_duration: Optional[str] = None
    frequency: Optional[str] = None
    credits: Optional[int] = None
    hours_total: Optional[int] = None
    hours_self_study: Optional[int] = None
    hours_presence: Optional[int] = None
    examination_achievements: Optional[str] = None
    repetition: Optional[str] = None
    recommended_prerequisites: Optional[str] = None
    content: Optional[str] = None
    learning_outcomes: Optional[str] = None
    teaching_methods: Optional[str] = None
    media: Optional[str] = None
    literature: Optional[str] = None
    lv_sws_lecturer: Optional[str] = None


def clean_page_headers(text):
    lines = text.split('\n')
    cleaned_lines = []
    
    skip_next = False
    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue
        if re.match(r'^[A-Z]+\d+:', line):
            if i + 1 < len(lines) and '[' in lines[i + 1] and ']' in lines[i + 1]:
                skip_next = True
                continue
                
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)

def get_new_module_header(lines, last_header):
    new_header = False
    pattern = r"^(.*?Modulbeschreibung\n)"
    match = re.search(pattern, lines, re.DOTALL)
    if match:
        result = " ".join(match.group(1).replace("Modulbeschreibung", "").split())
        if result != last_header:
            last_header = result
            new_header = True
    return new_header, last_header

def last_module(raw_page_text):
    return "Alphabetisches Verzeichnis der Modulbeschreibungen" in raw_page_text

def extract_modules(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            raw_full_text = ""
            raw_module_text = ""
            new_module_header = ""
            for page in pdf.pages:
                raw_page_text = page.extract_text() + "\n"
                new_module, new_module_header = get_new_module_header(raw_page_text, new_module_header)
                if new_module or last_module(raw_page_text):
                    if raw_full_text:
                        raw_full_text += raw_module_text + "\n"
                    raw_module_text = ""
                    raw_full_text += "[[TITLE]]: " + new_module_header + "\n"
                
                module_start_match = re.search(r'Modulbeschreibung\n', raw_page_text)
                if module_start_match:
                    module_niveau_match = re.search(r'Modulniveau:', raw_page_text)
                    if module_niveau_match:
                        raw_module_text = raw_page_text[module_niveau_match.start():]
                else:
                    raw_module_text += clean_page_headers(raw_page_text)
                
            return raw_full_text.split("\n\n")

 
    except Exception as e:
        print(f"Error processing PDF: {e}")
        return []
        
def sanitize_raw_module_text(raw_module_text: str):
    raw_module_text = re.sub(r'\* Die Zahl der Credits.*?ausgewiesene Wert\.', '', raw_module_text, flags=re.DOTALL)
    raw_module_text = re.sub(r'Modulhandbuch Department.*?\n', '', raw_module_text)
    raw_module_text = re.sub(r'Generiert am.*?\n', '', raw_module_text)
    raw_module_text = re.sub(r'Generiert am.*?$', '', raw_module_text)
    raw_module_text = re.sub(r'\b\d+ von \d+\b', '', raw_module_text)
    raw_module_text = re.sub(r'Für weitere Informationen.*?hier\.', '', raw_module_text, flags=re.DOTALL)
    raw_module_text = re.sub(r'\n\s*\n', '\n', raw_module_text)
    return raw_module_text.strip()

def extract_module_data(module_lines: str) -> Module:
    # Helper function to find index of line starting with a pattern
    module_lines = module_lines.split("\n")
    if len(module_lines) < 3:
        return None 
    def find_line_index(pattern: str) -> int:
        for i, line in enumerate(module_lines):
            if line.startswith(pattern):
                return i
        return -1
    
    # Helper function to extract content between two patterns
    def extract_between(start_pattern: str, end_pattern: str) -> str:
        start_idx = find_line_index(start_pattern)
        if start_idx == -1:
            return ""
        
        end_idx = -1
        for i in range(start_idx + 1, len(module_lines)):
            if module_lines[i].startswith(end_pattern):
                end_idx = i
                break
        
        if end_idx == -1:
            end_idx = len(module_lines)
            
        content = '\n'.join(module_lines[start_idx + 1:end_idx])
        return content.strip()

    # Get module ID and title from first line
    title_line = module_lines[0] if module_lines else ""
    title_match = re.search(r'\[\[TITLE\]\]: (.*?):(.*?)(?:\||$)', title_line)
    module_id = title_match.group(1).strip() if title_match else ""
    title = title_match.group(2).strip() if title_match else ""

    # Get basic info
    basic_info_idx = find_line_index("Modulniveau:")
    if basic_info_idx != -1 and basic_info_idx + 1 < len(module_lines):
        info_parts = module_lines[basic_info_idx + 1].split()
        i = 0
        skip_level = False
        if len(info_parts) < 4:
            skip_level = True
            level = ""

        if not skip_level:
            level = info_parts[i]
            i += 1

        language = info_parts[i]
        semester_duration = info_parts[i + 1]
        frequency = info_parts[i + 2]
        if frequency.endswith("/"):
            frequency += module_lines[basic_info_idx + 2]
    else:
        print(module_id + ": Issue reading first data row")
        level = language = semester_duration = frequency = None

    # Extract credits and hours
    credits_idx = find_line_index("Credits:")
    if credits_idx != -1 and credits_idx + 1 < len(module_lines):
        hours_line = module_lines[credits_idx + 1]

        if not module_lines[credits_idx + 2].startswith("Beschreibung"):
            hours_self_study = int(module_lines[credits_idx + 2])
        else:
            hours_self_study = None
        
        numbers_match = re.findall(r'(\d+)', hours_line)
        if len(numbers_match) >= 3:
            credits = int(numbers_match[0])
            hours_total = int(numbers_match[1])
            hours_presence = int(numbers_match[2])
        else:
            credits = int(numbers_match[0]) if numbers_match else None
            hours_total = None
            hours_presence = int(numbers_match[1]) if len(numbers_match) > 1 else None
            
    else:
        print(module_id + ": Issue reading second data row")
        credits = hours_total = hours_self_study = hours_presence = None

    # Extract all sections
    examination_achievements = extract_between(
        'Beschreibung der Studien-/ Prüfungsleistungen:', 
        'Wiederholungsmöglichkeit:'
    )
    
    repetition = extract_between(
        'Wiederholungsmöglichkeit:', 
        '(Empfohlene) Voraussetzungen:'
    )
    
    recommended_prerequisites = extract_between(
        '(Empfohlene) Voraussetzungen:', 
        'Inhalt:'
    )
    
    content = extract_between(
        'Inhalt:', 
        'Lernergebnisse:'
    )
    
    learning_outcomes = extract_between(
        'Lernergebnisse:', 
        'Lehr- und Lernmethoden:'
    )
    
    teaching_methods = extract_between(
        'Lehr- und Lernmethoden:', 
        'Medienform:'
    )
    
    media = extract_between(
        'Medienform:', 
        'Literatur:'
    )
    
    literature = extract_between(
        'Literatur:', 
        'Modulverantwortliche(r):'
    )
    
    lv_sws_lecturer = extract_between(
        'Modulverantwortliche(r):', 
        '[[TITLE]]'
    )

    if credits == None:
        print("HERE")

    return Module(
        module_id=module_id,
        title=title,
        level=level,
        language=language,
        semester_duration=semester_duration,
        frequency=frequency,
        credits=credits,
        hours_total=hours_total,
        hours_self_study=hours_self_study,
        hours_presence=hours_presence,
        examination_achievements=examination_achievements,
        repetition=repetition,
        recommended_prerequisites=recommended_prerequisites,
        content=content,
        learning_outcomes=learning_outcomes,
        teaching_methods=teaching_methods,
        media=media,
        literature=literature,
        lv_sws_lecturer=lv_sws_lecturer
    )

def save_modules_to_json(modules: list[Module], output_file: str):
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump([asdict(module) for module in modules], f, 
                 ensure_ascii=False, indent=2)


def main():
    # pdf_file_path = "input/Modulhandbuch_Department_Electrical_Engineering_15403417_20240910171354.pdf"
    pdf_file_path = "input/Modulhandbuch_Department_Computer_Engineering_15403408_20240910171122.pdf"
    
    modules = extract_modules(pdf_file_path)
    cleaned_modules = [sanitize_raw_module_text(module) for module in modules]
    cleaned_modules = [module for module in cleaned_modules if len(module.split('\n')) > 2]
    module_objects = [extract_module_data(module) for module in cleaned_modules]
    # module_objects = [m for m in module_objects if m is not None]

    print("Module count: " + str(len(module_objects)))

    # save txt
    with open('output/modules.txt', 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(cleaned_modules))
    
    save_modules_to_json(module_objects, 'output/modules.json')

if __name__ == "__main__":
    main()