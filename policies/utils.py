# policies/utils.py
import os
from typing import List, Dict, Any, Optional
import pdfplumber
from diff_match_patch import diff_match_patch
from django.conf import settings

dmp = diff_match_patch()

def extract_text_from_pdf(path: str) -> str:
    text_parts: List[str] = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            txt = p.extract_text()
            if txt:
                text_parts.append(txt)
    return "\n".join(text_parts)


def generate_diff_ops_and_patch(old_text: str, new_text: str) -> Dict[str, Any]:
    diffs = dmp.diff_main(old_text or "", new_text or "")
    dmp.diff_cleanupSemantic(diffs)
    ops = [{"op": op, "text": txt} for (op, txt) in diffs]
    patch = dmp.patch_make(old_text or "", new_text or "")
    patch_text = dmp.patch_toText(patch)
    return {"ops": ops, "patch_text": patch_text}


def apply_patch(base_text: str, patch_text: str) -> str:
    patch = dmp.patch_fromText(patch_text)
    new_text, results = dmp.patch_apply(patch, base_text or "")
    return new_text


def reconstruct_version(versions_qs, target_version: int) -> str:
    versions = list(versions_qs)
    if not versions:
        raise ValueError("No versions for this policy")

    ver_map = {v.version_number: v for v in versions}
    if target_version not in ver_map:
        raise ValueError("Requested version not found")

    # find nearest checkpoint <= target_version
    checkpoint = None
    for v in reversed(versions):
        if v.version_number <= target_version and v.is_checkpoint:
            checkpoint = v
            break
    if checkpoint is None:
        # fallback to version 1
        checkpoint = ver_map.get(1)
        if checkpoint is None:
            raise ValueError("No checkpoint or base version found")

    text = checkpoint.full_text or ""

    for vn in range(checkpoint.version_number + 1, target_version + 1):
        v = ver_map.get(vn)
        if v is None:
            raise ValueError(f"Missing version {vn}")
        if v.patch_text:
            text = apply_patch(text, v.patch_text)
        elif v.diff_ops:
            # fallback: stitch equal/insert
            parts: List[str] = []
            for op in v.diff_ops:
                if op["op"] in (0, 1):
                    parts.append(op["text"])
            text = "".join(parts)
        elif v.full_text:
            text = v.full_text
        else:
            raise ValueError(f"Version {vn} has no reconstruction info")
    return text


# LLM validate
import requests
import json

def llm_validate(policy_title: str, raw_text: str, template_sections: list = None) -> dict:
    """
    Generate structured policy content from raw user input.
    LLM reads raw text and organizes it based on the template sections provided.
    """
    template_sections = template_sections or []

    try:
        prompt = f"""
        You are given a raw policy text:

        {raw_text}

        Template Sections (for reference):
        {', '.join(template_sections)}

        Task:
        1. Organize the raw text into the template sections.
        2. Add missing content if necessary to make the policy complete.
        3. Suggest improvements or clarifications.
        4. Return a structured JSON with keys:
           - sections: list of section titles included
           - suggestions: list of improvement suggestions
           - final_text: the structured full policy text
        """

        res = requests.post(
            "http://192.168.8.9:11434/api/generate",
            json={"model": "llama3", "prompt": prompt, "stream": False},
            timeout=350
        )
        res.raise_for_status()
        data = res.json()
        raw_output = data.get("response", "").strip()

        return {
            "suggestions": raw_output
        }

        try:
            return json.loads(raw_output)
        except json.JSONDecodeError:
            start = raw_output.find("{")
            end = raw_output.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(raw_output[start:end])
            raise

    except Exception as e:
        print("LLM processing failed:", e)

    # Fallback if LLM fails: split by template sections or paragraphs
    sections = template_sections or [s.strip() for s in raw_text.split("\n\n") if s.strip()]
    return {
        "sections": sections,
        "suggestions": [],
        "final_text": raw_text
    }




###################################################################################################

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate

def generate_policy(title: str, headers: list, content: str) -> str:
    """
    Generate a structured policy where LLM maps raw text into correct headers
    without modifying spelling/letters/content.
    """

    # ---- Prompt ----
    map_template = f"""
    You are a policy organizer.
    Task: Place each sentence/paragraph from the user into the most relevant header.
    
    RULES:
    - Do NOT rewrite or rephrase.
    - Preserve user spelling, formatting, and words exactly as given.
    - If a piece of content does not match any header, put it under 'Uncategorized'.
    - Each header should appear once in the output, even if no content is found.

    Policy Title: "{title}"

    Headers:
    {headers}

    Raw Content:
    {{content}}

    Format the output like:

    # {title}

    ## Header1
    (mapped raw text)

    ## Header2
    (mapped raw text)

    ...
    """

    # ---- LLM ----
    llm = OllamaLLM(model="llama3.1", base_url="http://192.168.8.3:11434", temperature=0)

    prompt = PromptTemplate(input_variables=["content"], template=map_template)
    chain = prompt | llm

    return chain.invoke({"content": content})