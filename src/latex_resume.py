"""
LaTeX Resume Generator for EquiSkill.

Provides a professional ATS-friendly LaTeX resume template (based on
Jake's Resume), asks the LLM to fill it with user details, and
compiles to PDF when pdflatex is available.
"""
import os
import subprocess
import tempfile
import shutil
import urllib.parse
import logging
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Professional LaTeX resume template (Jake's Resume style — widely used,
# ATS-friendly, clean single-column layout)
# ---------------------------------------------------------------------------

LATEX_TEMPLATE = r"""
\documentclass[letterpaper,11pt]{article}

\usepackage[utf8]{inputenc}
\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage{tabularx}

\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

% Adjust margins
\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-0.5in}
\addtolength{\textheight}{1.0in}

\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

% Section formatting
\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

% Custom commands
\newcommand{\resumeItem}[1]{\item\small{#1 \vspace{-2pt}}}
\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}
\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #2 \\
    \end{tabular*}\vspace{-7pt}
}
\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}
\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}
\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}

\begin{document}

%% ===== HEADER =====
<<HEADER>>

%% ===== EDUCATION =====
<<EDUCATION>>

%% ===== EXPERIENCE =====
<<EXPERIENCE>>

%% ===== PROJECTS =====
<<PROJECTS>>

%% ===== SKILLS =====
<<SKILLS>>

\end{document}
"""

# ---------------------------------------------------------------------------
# Prompt that asks the LLM to fill the LaTeX template
# ---------------------------------------------------------------------------

FILL_TEMPLATE_PROMPT = r"""You are an expert LaTeX resume writer. Based on the conversation history below,
generate a COMPLETE, FILLED LaTeX resume using ONLY the template sections provided.

IMPORTANT RULES:
1. Output ONLY valid LaTeX code — no markdown, no ```latex fences, no explanations
2. Use the EXACT LaTeX commands from the template: \resumeSubheading, \resumeItem, \resumeProjectHeading, etc.
3. Fill ALL sections with the user's actual details from the conversation
4. If some details are missing, make reasonable professional-sounding placeholders marked with [EDIT]
5. Keep it to ONE page

Here are the section formats to use:

HEADER (replace with actual info):
\begin{{center}}
    \textbf{{\Huge \scshape FULL NAME}} \\ \vspace{{1pt}}
    \small PHONE $|$ \href{{mailto:EMAIL}}{{\underline{{EMAIL}}}} $|$
    \href{{LINKEDIN}}{{\underline{{LinkedIn}}}} $|$
    \href{{GITHUB}}{{\underline{{GitHub}}}} $|$
    LOCATION
\end{{center}}

EDUCATION:
\section{{Education}}
\resumeSubHeadingListStart
  \resumeSubheading{{University Name}}{{Location}}{{Degree — Major}}{{Dates}}
\resumeSubHeadingListEnd

EXPERIENCE:
\section{{Experience}}
\resumeSubHeadingListStart
  \resumeSubheading{{Job Title}}{{Dates}}{{Company Name}}{{Location}}
    \resumeItemListStart
      \resumeItem{{Achievement or responsibility}}
    \resumeItemListEnd
\resumeSubHeadingListEnd

PROJECTS:
\section{{Projects}}
\resumeSubHeadingListStart
  \resumeProjectHeading{{\textbf{{Project Name}} $|$ \emph{{Technologies Used}}}}{{Date}}
    \resumeItemListStart
      \resumeItem{{Description of the project}}
    \resumeItemListEnd
\resumeSubHeadingListEnd

SKILLS:
\section{{Technical Skills}}
\begin{{itemize}}[leftmargin=0.15in, label={{}}]
  \small{{\item{{
    \textbf{{Languages}}{{: Python, JavaScript, etc.}} \\
    \textbf{{Frameworks}}{{: TensorFlow, PyTorch, etc.}} \\
    \textbf{{Tools}}{{: Git, Docker, etc.}}
  }}}}
\end{{itemize}}

Now generate the COMPLETE LaTeX document. Start with \documentclass and include everything through \end{{document}}.
Use the preamble and custom commands from the template I showed you.

CONVERSATION HISTORY:
{conversation}
"""


def extract_conversation_text(chat_history) -> str:
    """Convert chat history into a readable string for the LLM."""
    parts = []
    for msg in chat_history:
        role = "User" if msg.type == "human" else "Assistant"
        parts.append(f"{role}: {msg.content}")
    return "\n\n".join(parts)


def generate_resume_latex(llm, chat_history) -> str:
    """
    Ask the LLM to generate a filled LaTeX resume based on the
    conversation history.
    """
    conversation_text = extract_conversation_text(chat_history)

    prompt = ChatPromptTemplate.from_template(FILL_TEMPLATE_PROMPT)
    chain = prompt | llm
    response = chain.invoke({"conversation": conversation_text})

    latex_code = response.content.strip()

    # Clean up any markdown fences the LLM might add
    if latex_code.startswith("```"):
        lines = latex_code.split("\n")
        # Remove first and last fence lines
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        latex_code = "\n".join(lines)

    return latex_code


def compile_latex_to_pdf(latex_code: str) -> tuple[bytes | None, str]:
    """
    Compile LaTeX to PDF using pdflatex.

    Returns:
        (pdf_bytes, tex_path) — pdf_bytes is None if compilation failed.
    """
    # Check if pdflatex is available
    pdflatex_path = shutil.which("pdflatex")

    # Create a temp directory for compilation
    tmpdir = tempfile.mkdtemp(prefix="equiskill_resume_")
    tex_path = os.path.join(tmpdir, "resume.tex")
    pdf_path = os.path.join(tmpdir, "resume.pdf")

    # Write the .tex file
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(latex_code)

    if not pdflatex_path:
        logger.info("pdflatex not found — returning .tex only")
        return None, tex_path

    try:
        # Run pdflatex twice (for references/layout)
        for _ in range(2):
            result = subprocess.run(
                [pdflatex_path, "-interaction=nonstopmode", "-output-directory", tmpdir, tex_path],
                capture_output=True,
                text=True,
                timeout=60,
            )

        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            return pdf_bytes, tex_path
        else:
            logger.warning("pdflatex ran but no PDF produced. Log:\n%s", result.stdout[-500:])
            return None, tex_path

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.warning("pdflatex failed: %s", e)
        return None, tex_path


def get_overleaf_url(latex_code: str) -> str:
    """
    Generate a URL that opens the LaTeX code directly in Overleaf
    (free online LaTeX editor) for compilation.
    """
    # Overleaf supports opening via encoded snippet
    encoded = urllib.parse.quote(latex_code, safe="")
    return f"https://www.overleaf.com/docs?snip_uri=data:text/plain;charset=utf-8,{encoded}"
