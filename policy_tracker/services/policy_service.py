import requests
import json
from decouple import config
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from ..models import Organization, OrgPolicy, PolicyVersion
from ..utils.diff_utils import compute_html_diff, apply_diff

AI_CHAT_URL = config("AI_CHAT_URL")


class PolicyAIService:
    """Service class for AI-related policy operations"""
    
    @staticmethod
    def extract_title_version_from_pdf(pdf_text):
        """
        Extract policy title and version from PDF text content using AI
        """
        prompt = f"""
        Analyze the following PDF text content and extract the policy title and version number.
        
        PDF CONTENT:
        {pdf_text[:4000]}  # Limit content to avoid token limits
        
        INSTRUCTIONS:
        1. Identify the main policy title - look for the most prominent heading or document title
        2. Identify the version number - look for patterns like "Version X.X", "v1.0", "Rev 2.3", etc.
        3. If you find both title and version, return them in JSON format
        4. If title is missing, indicate which field is missing
        5. If version is missing, indicate which field is missing
        6. If both are missing, indicate both are missing
        
        RETURN FORMAT (JSON):
        {{
            "title": "Extracted Policy Title or null if not found",
            "version": "Extracted Version Number or null if not found"
        }}
        
        Return ONLY the JSON object without any additional text or explanations.
        """
        
        payload = {"query": prompt}
        try:
            response = requests.post(AI_CHAT_URL, json=payload, timeout=30)
            response.raise_for_status()
            response_text = response.json().get("response", "").strip()
            
            # Clean the response to extract JSON
            response_text = response_text.replace('```json', '').replace('```', '').strip()
            
            extracted_data = json.loads(response_text)
            
            missing_fields = []
            if not extracted_data.get("title"):
                missing_fields.append("title")
            if not extracted_data.get("version"):
                missing_fields.append("version")
            
            if missing_fields:
                return {
                    "status": 400,
                    "message": f"Missing required fields from PDF: {', '.join(missing_fields)}",
                    "missing_fields": missing_fields,
                    "extracted_data": extracted_data
                }, None
            else:
                return {
                    "status": 200,
                    "message": "Title and version successfully extracted from PDF",
                    "extracted_data": extracted_data
                }, extracted_data
                
        except requests.Timeout:
            return {
                "status": 408,
                "message": "AI service timeout",
                "missing_fields": ["title", "version"],
                "extracted_data": {"title": None, "version": None}
            }, None
        except Exception as e:
            print(f"PDF title/version extraction failed: {str(e)}")
            return {
                "status": 400,
                "message": f"Failed to extract title and version from PDF: {str(e)}",
                "missing_fields": ["title", "version"],
                "extracted_data": {"title": None, "version": None}
            }, None

    @staticmethod
    def format_html_with_ai(template, title, department, category):
        """
        Send policy information to AI service to generate complete policy HTML.
        """
        version = "V1"
        company_name = "Your Company"
        company_logo = "logo"
        example_template = """""<!doctype html>
                        <html lang="en">
                        <head>
                        <meta charset="utf-8">
                        <meta name="viewport" content="width=device-width,initial-scale=1">
                        <title>Information Security Policy</title>
                        <meta name="description" content="Organization Information Security Policy">
                        <style>
                            :root{
                            --bg:#f7f9fc; --card:#ffffff; --accent:#0b5cff; --muted:#6b7280; --maxw:960px;
                            --radius:12px; --gap:18px;
                            }
                            html,body{min-height:100vh;margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,'Helvetica Neue',Arial;color:#0f1724;background:var(--bg);}
                            .wrap{width:100%;min-height:100vh;margin:0;padding:24px;box-sizing:border-box;display:flex;flex-direction:column}
                            header{display:flex;align-items:center;justify-content:space-between;gap:0;margin-bottom:18px;flex-wrap:wrap}
                            .brand{display:flex;flex-direction:column;flex:1;text-align:center}
                            .logo img{height:40px;width:auto}
                            h1{margin:0;font-size:1.4rem}
                            p.lead{margin:6px 0 0;color:var(--muted)}
                            .card{background:var(--card);border-radius:var(--radius);box-shadow:0 6px 18px rgba(10,20,40,.06);padding:20px}
                            nav.toc{margin:12px 0 20px}
                            .toc-list{display:flex;flex-wrap:wrap;gap:8px}
                            .toc-list a{background:#eef2ff;padding:8px 12px;border-radius:999px;text-decoration:none;color:var(--accent);font-size:.9rem}
                            section{margin-top:20px}
                            h2{font-size:1.05rem;margin:0 0 8px}
                            .meta{font-size:.92rem;color:var(--muted);margin-bottom:12px}
                            .cols{display:flex;flex-direction:column;gap:12px;flex:1;width:100%}
                            .sub{margin:8px 0;padding-left:8px;border-left:3px solid #eef3ff}
                            details{margin:8px 0}
                            pre{white-space:pre-wrap;background:#0b1220;color:#e6eef8;padding:12px;border-radius:8px;overflow:auto}
                            footer{margin-top:28px;font-size:.9rem;color:var(--muted);text-align:center;flex-shrink:0}
                            @media(min-width:880px){.cols{flex-direction:row;width:100%;max-width:none}
                            main{flex:1}
                            aside{width:320px;flex-shrink:0}
                            nav.toc{}
                            .wrap{padding:24px 0}
                            }
                            @media(min-width:1200px){.wrap{padding:24px 48px}}
                            .print-hide{display:inline-block}
                            @media print{body{background:white} .wrap{box-shadow:none;padding:0} .print-hide{display:none}}
                        </style>
                        </head>
                        <body>
                        <div class="wrap">
                            <header>
                            <div class="brand">
                                <h1>Information Security Policy</h1>
                            </div>
                            <div class="logo">
                                <img src="https://via.placeholder.com/120x40/0b5cff/ffffff?text=Company+Logo" alt="Company Logo">
                            </div>
                            </header>

                            <div class="cols">
                            <main class="card">
                                <nav class="toc print-hide" aria-label="Table of contents">
                                <strong>Contents</strong>
                                <div class="toc-list">
                                    <a href="#introduction">Introduction</a>
                                    <a href="#scope">Scope</a>
                                    <a href="#leadership">Leadership</a>
                                    <a href="#roles">Roles & Responsibilities</a>
                                    <a href="#compliance">Policy Compliance</a>
                                    <a href="#training">Staff Contracts & Training</a>
                                    <a href="#objectives">Security Objectives</a>
                                    <a href="#risk">Risk Management</a>
                                    <a href="#operation">ISMS Operation</a>
                                    <a href="#procedures">Operating Procedures</a>
                                    <a href="#reporting">Reporting</a>
                                    <a href="#monitoring">Monitoring & Review</a>
                                </div>
                                </nav>

                                <section id="introduction">
                                <h2>Introduction</h2>
                                <p class="meta">Purpose and confidentiality</p>
                                <p>
                                    The Information Security Policy defines the security standards of the organization as approved by management. It describes the foundations for Information Security, Risk, and Compliance functions. The contents of this document and related documents are confidential and shall only be accessible to external parties under a signed Non-Disclosure Agreement (NDA) and explicit approval by management.
                                </p>
                                </section>

                                <section id="scope">
                                <h2>Scope</h2>
                                <p class="meta">People, technology, processes and legal entity</p>
                                <p>
                                    This program covers people, technology, and processes that build, maintain, and distribute the organization's software and related services, including On-Premise, SaaS, Consulting, and Support. The legal entity in scope is the organization incorporated in <em>[location]</em>.
                                </p>
                                <p>
                                    The program aims to protect information assets, intellectual property, and reputation by implementing risk and compliance programs to meet regulations and contractual obligations.
                                </p>
                                </section>

                                <section id="leadership">
                                <h2>Leadership</h2>
                                <p class="meta">Management support and responsibilities</p>
                                <p>
                                    Management demonstrates active support for information security through regular communications and participation in security initiatives to cultivate a strong security culture.
                                </p>
                                <div class="sub">
                                    <h3>Management Responsibilities</h3>
                                    <ul>
                                    <li>Brief personnel on security roles before granting access.</li>
                                    <li>Provide role-specific security expectations.</li>
                                    <li>Mandate adherence to information security policies.</li>
                                    <li>Design reporting lines and control activities across organizational units.</li>
                                    <li>Establish responsibility and accountability for policy execution within business units.</li>
                                    </ul>
                                </div>
                                </section>

                                <section id="roles">
                                <h2>Roles &amp; Responsibilities</h2>
                                <p class="meta">Organizational structure and duties</p>
                                <p>
                                    Roles are defined, assigned, and limited with consideration for security, availability, processing integrity, confidentiality, and privacy. The organization is divided into functions: Management, Information Security Team, IT, Finance & HR, and Development. Responsibilities are documented and communicated via awareness sessions and role-specific training.
                                </p>

                                <div class="sub">
                                    <h3>Board of Directors Oversight</h3>
                                    <p>
                                    The Board functions independently from management to oversee internal control systems, including interaction monitoring with external parties. Board members include independent members and may engage external advisors or subcommittees. The Board's security and risk expertise are periodically evaluated.
                                    </p>
                                </div>
                                </section>

                                <section id="compliance">
                                <h2>Information Security Policy Compliance</h2>
                                <p class="meta">Expectations and disciplinary process</p>
                                <p>
                                    All staff and relevant interested parties must comply with the policy and related procedures. Violations will be addressed via a formal disciplinary process with a graduated response that considers severity, intent, and training.
                                </p>
                                </section>

                                <section id="training">
                                <h2>Staff Contracts &amp; Training</h2>
                                <p class="meta">Confidentiality, IP and competence</p>
                                <p>
                                    All personnel shall have contracts including confidentiality and IP clauses. Management supports training and education to align staff skills with organizational needs. Post-employment security responsibilities will be defined and enforced.
                                </p>
                                <p>
                                    Resources and planning time will be allocated for security-related processes and controls; management commits to ongoing professional education.
                                </p>
                                </section>

                                <section id="control-performance">
                                <h2>Control Activities Performance &amp; Corrective Action</h2>
                                <p>
                                    Control activities are performed by competent personnel. Deviations or deficiencies are investigated promptly and corrective actions are implemented to ensure continuous improvement.
                                </p>
                                </section>

                                <section id="objectives">
                                <h2>Information Security Objectives</h2>
                                <p class="meta">Targets, review and business continuity</p>
                                <p>
                                    The organization documents security objectives, targets, and achievements and reviews them during management reviews. Priorities for mission and objectives are communicated and integrated into the Information Security framework to guide risk decisions. The organization maintains appropriate security during business disruptions.
                                </p>
                                </section>

                                <section id="context">
                                <h2>Context of the Organization</h2>
                                <p>
                                    The organization recognises internal constraints such as budgets and reliance on third parties, and external drivers such as customer security expectations and regulatory obligations. This context informs cybersecurity roles, responsibilities and risk decisions.
                                </p>
                                </section>

                                <section id="interested-parties">
                                <h2>Contact with Interested Parties</h2>
                                <p>
                                    Regular communication with interested parties (legal, regulatory, customers, partners, auditors) is maintained to track security trends and obligations. Consideration is given to how external interactions affect reporting lines and responsibilities.
                                </p>
                                <h3>Identified Interested Parties</h3>
                                <ul>
                                    <li>Customers</li>
                                    <li>Auditors</li>
                                    <li>Partners</li>
                                    <li>Media</li>
                                    <li>Competitors</li>
                                    <li>Organization's staff</li>
                                </ul>
                                </section>

                                <section id="risk">
                                <h2>Risk Management</h2>
                                <p class="meta">Assessment, treatment and governance</p>
                                <p>
                                    A risk management process is established to identify, assess, treat and monitor risks. Cybersecurity risk management is integrated into governance to ensure decisions consider regulatory, legal, environmental, operational, and strategic contexts.
                                </p>
                                <ul>
                                    <li>Document risk-related decisions at all levels.</li>
                                    <li>Communicate risk information to appropriate management levels.</li>
                                    <li>Leadership endorses and resources the risk strategy.</li>
                                    <li>Maintain records of governance and risk activities.</li>
                                </ul>
                                </section>

                                <section id="operation">
                                <h2>Information Security Management System (ISMS) Operation</h2>
                                <p>
                                    The ISMS is supported by policies, standards and procedures that are reviewed regularly. Documentation is controlled, and exceptions are approved and tracked. Management ensures financial and human resources are available for ISMS operation.
                                </p>
                                <p>
                                    Competence is evaluated before engagement with staff or suppliers, and regular training is provided. The ISMS includes periodic reassessment of controls to ensure relevance and effectiveness.
                                </p>
                                </section>

                                <section id="procedures">
                                <h2>Documented Operating Procedures</h2>
                                <p>
                                    Procedures shall be prepared when activities are new, rare, require consistency, or need handover. They shall include responsible staff, secure installation/configuration, processing and handling of information, backup and resilience, scheduling, error handling, escalation contacts, recovery procedures, audit trail management, monitoring and maintenance.
                                </p>
                                <p>Procedures are reviewed and significant changes are authorised and tracked through change management.</p>
                                </section>

                                <section id="contact-authorities">
                                <h2>Contact with Authorities and Special Interest Groups</h2>
                                <p>
                                    In case of incidents breaching legal/regulatory obligations, management must be informed and remedial actions taken. If management fails to act, staff may contact relevant authorities. The organization maintains communication with special interest groups to stay current on security topics.
                                </p>
                                </section>

                                <section id="legislation">
                                <h2>Applicable Legislations</h2>
                                <p>
                                    The organization shall consider applicable laws such as GDPR, CCPA, national Data Protection Acts, and industry-specific regulations, and incorporate them into the ISMS context.
                                </p>
                                </section>

                                <section id="reporting">
                                <h2>Reporting</h2>
                                <p>
                                    Regular organisational meetings discuss main risks, control performance and document updates. Agreements and action plans should be recorded or executed to correct ISMS deficiencies.
                                </p>
                                <h3>Confidential Reporting Channels</h3>
                                <p>
                                    A confidential reporting channel allows anonymous or limited-identity reporting of policy violations.
                                </p>
                                </section>

                                <section id="monitoring">
                                <h2>Monitoring and Review</h2>
                                <p>
                                    The organization monitors ISMS effectiveness via document reviews, performance tracking, and compliance audits. Management and the Board conduct evaluations and remediate internal control deficiencies promptly. Internal audits are performed on a planned cycle ensuring policies and controls are audited at least once every three years.
                                </p>
                                <p>
                                    The organization identifies areas for improvement and implements corrective and preventive actions as part of continual improvement.
                                </p>
                                </section>

                            </main>

                            <aside class="card">
                                <strong>Quick actions</strong>
                                <ul>
                                <li><a href="#introduction">Jump to Introduction</a></li>
                                <li><a href="#scope">Edit Scope</a></li>
                                <li><a href="#legislation">Add Applicable Laws</a></li>
                                </ul>

                                <hr>
                                <strong>Document metadata</strong>
                                <p class="meta">Status: Draft<br>Owner: Information Security Team<br>Review cycle: Annual</p>

                                <hr>
                                <strong>Version history</strong>
                                <ol>
                                <li>V1 — Initial draft</li>
                                </ol>

                                <hr>
                            </aside>
                            </div>

                            <footer>
                            <p>Created for internal use. For changes, contact the Information Security Team.</p>
                            </footer>
                        </div>
                        </body>
                        </html>"""
        
        if template:
            prompt = f"""You are a senior UI/UX designer and full-stack developer specializing in corporate policy documents.

                        Generate a **complete, standalone, visually stunning HTML policy document** with **modern, colorful, professional styling**. 

                        It should exacrly look like {example_template}

                        **IMPORTANT:**
                        - No Pagination at all - means it should not say anythin like page 1 of 5, or 2 of 5
                        - DO NOT repeat the title after the header section
                        - Return ONLY the HTML document, no other text
                        - Start directly with <!DOCTYPE html>
                        - End with </html>
                                    """
        
        payload = {"query": prompt}

        try:
            response = requests.post(AI_CHAT_URL, json=payload, timeout=100)
            response.raise_for_status()
            response_text = response.json().get("response", "").strip()

            # Clean response
            if response_text.startswith('"') and response_text.endswith('"'):
                response_text = response_text[1:-1]
            if response_text.startswith('```html'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # Optionally slice starting from <h1> for consistency
            start_index = response_text.find("<h1>")
            if start_index >= 0:
                response_text = response_text[start_index:]

            return {"status": 200, "message": "Policy generated successfully by LLM"}, response_text

        except requests.Timeout:
            return {"status": 408, "message": "AI service timeout"}, ""
        except Exception as e:
            print(f"AI policy generation failed: {str(e)}")
            return {"status": 500, "message": f"AI policy generation failed: {str(e)}"}, ""



class PolicyVersionService:
    """Service class for policy version operations"""
    
    @staticmethod
    @transaction.atomic
    def create_or_update_policy_with_version(title, html_template, version, org, created_by, updated_by, description=None):
        """
        Create a new OrgPolicy or update an existing one, recording a PolicyVersion diff.
        """
        formatted_html = html_template
        
        org_policy, created = OrgPolicy.objects.select_for_update().get_or_create(
            title=title,
            organization=org,
            defaults={
                'template': formatted_html,
                'policy_type': 'existingpolicy',
                'created_by': created_by,
                'updated_by': updated_by,
            },
        )

        if created:
            print(f"Creating new OrgPolicy: {title} with version: {version} for organization: {org.id}")
            # New policy - create first version with empty diff
            old_html = ""
            new_html = formatted_html
            
            diff_json = compute_html_diff(old_html, new_html)
            
            policy_version = PolicyVersion.objects.create(
                org_policy=org_policy,
                version=version,
                diff_data=diff_json,
                status='published',
                created_by=created_by,
                updated_by=updated_by,
            )
            print(f"New OrgPolicy created successfully. OrgPolicy ID: {org_policy.id}, PolicyVersion ID: {policy_version.id}")
            return {
                "org_policy_id": org_policy.id,
                "policy_version_id": policy_version.id,
                "version_number": version,
                "created": True,
            }

        print(f"Updating existing OrgPolicy: {title} to version {version} for organization: {org.id}")
        print(f"Old HTML length: {len(org_policy.template or '')}")
        print(f"New HTML length: {len(formatted_html)}")
        
        # Existing policy: compute diff vs current template
        old_html = org_policy.template or ""
        new_html = formatted_html
        
        diff_json = compute_html_diff(old_html, new_html)
        print(f"Diff computed. Changes: {len(diff_json.get('changes', []))}")

        # Update OrgPolicy template
        org_policy.template = new_html
        org_policy.updated_by = updated_by
        org_policy.save()

        # Create new PolicyVersion with diff
        policy_version = PolicyVersion.objects.create(
            org_policy=org_policy,
            version=version,
            diff_data=diff_json,
            status='published',
            created_by=created_by,
            updated_by=updated_by,
        )
        
        print(f"OrgPolicy updated successfully. New version: {version}, PolicyVersion ID: {policy_version.id}")
        return {
            "org_policy_id": org_policy.id,
            "policy_version_id": policy_version.id,
            "version_number": version,
            "created": False,
        }

    @staticmethod
    def reconstruct_policy_html_at_version(org_policy_id, target_version):
        """
        Reconstruct policy HTML for a specific version using optimal checkpoint strategy.
        """
        try:
            # Get all versions for this policy
            all_versions = list(PolicyVersion.objects.filter(
                org_policy_id=org_policy_id
            ).order_by('version'))
            
            if not all_versions:
                raise ObjectDoesNotExist("No versions found for this policy")
            
            # Find target version
            target_version_obj = None
            for version in all_versions:
                if version.version == target_version:
                    target_version_obj = version
                    break
            
            if not target_version_obj:
                raise ObjectDoesNotExist(f"Version {target_version} not found")
            
            # Find the nearest checkpoint BEFORE the target version
            nearest_checkpoint = None
            for version in reversed(all_versions):
                if version.version <= target_version and version.checkpoint_template:
                    nearest_checkpoint = version
                    break
            
            if nearest_checkpoint:
                print(f"Using checkpoint at version {nearest_checkpoint.version} to reconstruct version {target_version}")
                return PolicyVersionService._reconstruct_from_checkpoint(nearest_checkpoint, target_version_obj, all_versions)
            else:
                # No checkpoint found, reconstruct from beginning
                print(f"No checkpoint found, reconstructing version {target_version} from beginning")
                return PolicyVersionService._reconstruct_sequentially(all_versions, target_version)
            
        except Exception as e:
            print(f"Error reconstructing policy HTML: {str(e)}")
            raise e

    @staticmethod
    def _reconstruct_from_checkpoint(checkpoint_version, target_version, all_versions):
        """Reconstruct HTML from checkpoint to target version"""
        current_html = checkpoint_version.checkpoint_template or ""
        start_applying = False
        
        for version in all_versions:
            if version.version == checkpoint_version.version:
                start_applying = True
                continue
                
            if start_applying and version.diff_data:
                current_html = apply_diff(current_html, version.diff_data)
                
            if version.version == target_version.version:
                break
                
        return current_html

    @staticmethod
    def _reconstruct_sequentially(all_versions, target_version):
        """Reconstruct HTML sequentially from beginning to target version"""
        current_html = ""
        
        for version in all_versions:
            if version.diff_data:
                current_html = apply_diff(current_html, version.diff_data)
                
            if version.version == target_version:
                break
                
        return current_html


# Legacy function aliases for backward compatibility
def extract_title_version_from_pdf(pdf_text):
    """Legacy function - use PolicyAIService.extract_title_version_from_pdf instead"""
    return PolicyAIService.extract_title_version_from_pdf(pdf_text)

def format_html_with_ai(template, title, department, category):
    """Legacy function - use PolicyAIService.format_html_with_ai instead"""
    return PolicyAIService.format_html_with_ai(template, title, department, category)

def create_or_update_policy_with_version(title, html_template, version, org, created_by, updated_by, description=None):
    """Legacy function - use PolicyVersionService.create_or_update_policy_with_version instead"""
    return PolicyVersionService.create_or_update_policy_with_version(
        title, html_template, version, org, created_by, updated_by, description
    )

def reconstruct_policy_html_at_version(org_policy_id, target_version):
    """Legacy function - use PolicyVersionService.reconstruct_policy_html_at_version instead"""
    return PolicyVersionService.reconstruct_policy_html_at_version(org_policy_id, target_version)


# =============================================================================
# UNUSED FUNCTIONS (COMMENTED OUT FOR NOW)
# =============================================================================

"""
def analyze_policy_content(content, policy_titles):
    # Send content to AI service for policy analysis
    # This function is not currently used in the main workflow
    pass

def link_policy_to_organization(org_id, policy_title):
    # Link policy to organization if match found
    # This function is not currently used in the main workflow
    pass

def get_all_policy_titles():
    # Get all policy titles from database
    # This function is not currently used in the main workflow
    pass
"""