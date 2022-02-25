import re
import datetime

 
 
def is_valid_email(email):
    regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    if(re.fullmatch(regex, email)):
        return True
    else:
        return False
        
def is_int(string):
    result = None
    try:
        result = int(string)
    except Exception as e:
        result = None
    return result
    
def tsToEpoch(string):
    return int(datetime.datetime.strptime(string, "%y-%m-%d %H:%M").timestamp())

def filterNonPrint(string):
    filterChar = list(s for s in string if ( s.isprintable() or s == "\n") )
    return ''.join(filterChar)

def removeSufficPrefix(string):
    matches = re.search(r"\n(.*)can", filterNonPrint(string), re.DOTALL)
    if(matches):
        return matches.group(1).strip()
    else:
        return string
 
def singleLine(regex,string):
    matches = re.search(regex, string)
    if(matches):
        return filterNonPrint(matches.group(1).strip())
    else:
        return None

def multiLine(regex,string):
    matches = re.findall(regex, string, re.MULTILINE)
    if(matches):
        return matches
    else:
        return []
           