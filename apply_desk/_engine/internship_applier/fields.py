"""Match and fill form controls; final readback is a separate step."""
import datetime as dt
import re
def norm(s):
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', (s or '').lower().replace('✱', '')).split()).replace(' required', '')

def similar(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if min(len(a), len(b)) >= 8 and (a.startswith(b) or b.startswith(a)):
        return 0.9
    ta, tb = set(a.split()), set(b.split())
    return len(ta & tb) / len(ta | tb)

# Approved spellings of the same place, school or degree. A choice is still picked only by exact option text.
ALIASES = {
    'united states': ['United States of America', 'United States +1', 'United States of America +1'],
    'bachelor s': ["Bachelor's Degree", 'Bachelor of Science'],
    'university of michigan': ['University of Michigan, Ann Arbor', 'University of Michigan - Ann Arbor', 'University of Michigan, Ann Arbor (UMich)'],
    'university of michigan ann arbor': ['University of Michigan', 'University of Michigan - Ann Arbor', 'University of Michigan, Ann Arbor (UMich)'],
    'ann arbor': ['Ann Arbor, Michigan, United States', 'Ann Arbor, MI, United States', 'Ann Arbor, MI, USA'],
    'ann arbor mi': ['Ann Arbor, Michigan, United States', 'Ann Arbor, MI, United States', 'Ann Arbor, Michigan', 'Ann Arbor, MI, USA'],
}


def best(options, answer):
    """Choices need exact text; approved aliases are explicit alternatives."""
    alternatives = answer.split('||')
    for alternative in alternatives + [alias for a in alternatives for alias in ALIASES.get(norm(a), [])]:
        matches = [o for o in options if norm(o) == norm(alternative)]
        unique = list(dict.fromkeys(matches))
        if len(unique) == 1:
            return unique[0]
    return None

CONSENT = r'certif|attest|signature|terms (and|&) conditions|terms of (use|service)|consent|i agree|agree to|acknowledg|privacy|policy|pledge|declar|truthful|accurate and complete'

CHOICE = ('radio', 'buttons', 'checkgroup', 'select', 'combobox', 'checkbox')

def keyed(fields):
    """Index scanned fields by kind, question text and repeat number, which survive re-renders (element markers don't)."""
    out, seen = {}, {}
    for f in fields:
        base = f"{f['kind']}|{norm(f['label'])}"
        seen[base] = seen.get(base, 0) + 1
        out[f"{base}|{seen[base]}"] = f
    return out

def kit_required(field, role):
    """The job API's required flag; Ashby's live inputs don't carry one."""
    match = max(role['fields'], key=lambda f: similar(f['label'], field['label']), default=None)
    if match and field['kind'] in CHOICE and not match.get('options') and match.get('type') in {'text','input_text','input_email','input_tel','ShortText','Text','LongText','Email','Phone','PhoneNumber'}:
        return False  # SMS consent controls beside a required phone input are different questions
    if match and field['kind']=='file' and match.get('type') not in {'file','File','input_file','Resume','ResumeUpload'}:
        return False
    return bool(match and similar(match['label'], field['label']) >= 0.75 and match.get('required'))

def plan_for(field, role):
    """Return (answer, who) for a live field: the kit's answer for the matching question, else a system default."""
    if re.search(r'pronoun', field['label'], re.I):
        return '', 'skip'
    match = max(role['fields'], key=lambda f: similar(f['label'], field['label']), default=None)
    if match and similar(match['label'], field['label']) >= 0.75:
        ans, who = match['answer'], match['who']
        if re.match(r'https?://|\S+@\S+$|\(\d{3}\)', ans or '') and len(field['label']) > 45:
            return '', 'you' if field['required'] else 'skip'  # 'Take this quiz: https://x.github.io' is not asking for a GitHub link
        return ans, who
    for pat, ans in role['defaults']:
        if len(field['label']) <= 45 and re.search(pat, field['label'], re.I):
            return ans, 'profile' if ans else 'you'
    return '', 'you' if field['required'] else 'skip'

def fill_field(page, f, ans, pdf):
    loc = lambda i: page.locator(f'[data-apply-idx="{i}"]')
    k = f['kind']
    if k == 'file':
        if not re.search(r'resume|cv\b', f['label'], re.I):
            return False
        loc(f['idx']).set_input_files(str(pdf))
        return True
    if k == 'text':
        el = loc(f['idx'])
        if el.evaluate("e=>e.classList.contains('location-input')"):
            el.fill('')
            el.press_sequentially(ans, delay=15)
            options = el.locator('xpath=..').locator('.dropdown-location:visible')
            for _ in range(10):
                page.wait_for_timeout(400)
                texts = options.all_inner_texts()
                chosen = best(texts, ans)
                if chosen:
                    options.nth(texts.index(chosen)).click()
                    f['_expected_value'] = chosen
                    return norm(el.input_value()) == norm(chosen)
            el.fill('')
            return False
        m = re.fullmatch(r'([A-Za-z]+)\.? (\d{4})', ans.strip())
        if m and el.evaluate("e => /date/i.test(e.placeholder + ' ' + e.className + ' ' + e.type)"):
            if not f.get('allow_month_start'):
                return False  # month precision never silently invents an exact date
            mon = dt.datetime.strptime(m[1][:3].title(), '%b').month  # date pickers want MM/DD/YYYY; the 1st stands in for 'month and year'
            ans = f'{mon:02d}/01/{m[2]}'
        f['_expected_value'] = ans
        el.fill(ans)
        if re.search(r'date|when', f['label'], re.I):
            page.keyboard.press('Escape')  # date pickers otherwise cover the fields below
        el.evaluate('e => e.blur()')
        got = el.input_value()
        return norm(got) == norm(ans) or (re.sub(r'\D', '', got)[-10:] == re.sub(r'\D', '', ans)[-10:] != '' and 'phone' in f['label'].lower())
    if k == 'select':
        opt = best(f['options'], ans)
        if not opt:
            return False
        loc(f['idx']).select_option(label=opt)
        f['_expected_value'] = opt
        return True
    if k in ('radio', 'buttons', 'checkgroup'):
        ok = False
        selected = []
        for want in [a.strip() for a in (ans.split(';') if k == 'checkgroup' else [ans])]:
            opt = best([o['text'] for o in f['options']], want)
            if opt:
                i = next(o['idx'] for o in f['options'] if o['text'] == opt)
                (loc(i).check(force=True) if k != 'buttons' else loc(i).click(force=True))
                ok = True
                selected.append(opt)
        f['_expected_value'] = '; '.join(selected)
        return ok and len(selected) == len(ans.split(';') if k == 'checkgroup' else [ans])
    if k == 'combobox':
        el = loc(f['idx'])
        selected = []
        for choice in [a.strip() for a in ans.split(';')]:
            opts, opt = page.locator('[role=option]:visible'), None
            for want in [w.strip() for w in choice.split('||')]:  # 'Computer Engineering || Engineering': first one the list has
                control = el.locator('xpath=ancestor::*[contains(@class,"select__control")][1]')
                if control.count() and el.get_attribute('aria-expanded') != 'true':
                    control.click(timeout=5000)
                el.focus()
                el.fill('')
                el.press_sequentially(want[:40], delay=15)
                for _ in range(10):  # async lists (schools, cities) arrive late
                    page.wait_for_timeout(400)
                    texts = opts.all_inner_texts()
                    opt = best(texts, want)
                    if opt:
                        break
                if opt:
                    break
            if opt is None:
                page.keyboard.press('Escape')
                el.fill('')
                return False
            opts.nth(texts.index(opt)).click(force=True)
            selected.append(opt)
            page.wait_for_timeout(200)
        f['_expected_value'] = '; '.join(selected)
        return True
    if k == 'checkbox':
        if ans.lower() in ('yes', 'true') and not re.search(r'certif|attest|agree|consent|acknowledg|terms|privacy|sms|text message|whatsapp', f['label'], re.I):
            loc(f['idx']).check(force=True)
            return True
    return False
