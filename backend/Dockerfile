FROM python:3.12-slim

# xelatex + the LaTeX packages the CV pipeline needs to reproduce the user's
# main.tex template exactly (titlesec, tabularx, enumitem, fontawesome5,
# eso-pic, lastpage, changepage, paracol, needspace, tikz, charter, etc. --
# see app/services/latex/render.py and app/services/latex/safety.py's
# ALLOWED_PACKAGES for the authoritative list), plus poppler-utils for
# pdftotext/pdfinfo used to validate compiled PDFs.
RUN echo 'Acquire::http::Pipeline-Depth "0";' > /etc/apt/apt.conf.d/99no-pipelining \
    && echo 'Acquire::Retries "5";' >> /etc/apt/apt.conf.d/99no-pipelining
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-xetex \
    texlive-latex-recommended \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-pictures \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

COPY backend/ .
RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python scripts/seed_profile.py && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
