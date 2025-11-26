"""
Context builder - extracts relevant report sections for slide generation.
"""

import logging
from typing import Dict, List
from itertools import product, chain

logger = logging.getLogger(__name__)


class ContextBuilder:
    """
    Builds selective context from report knowledge for efficient slide generation.
    
    This class handles the logic for extracting only relevant report sections
    per slide, reducing token usage while maintaining context quality.
    """
    
    @staticmethod
    def extract_relevant_report_sections(
        outline: Dict,
        report_knowledge: Dict,
        max_sections_per_slide: int = 5
    ) -> Dict[int, List[Dict]]:
        """
        Extract only relevant report_knowledge.sections for each slide based on topic matching.
        
        Uses keyword-based matching to identify which report sections are relevant to each slide.
        
        Args:
            outline: Presentation outline with slides
            report_knowledge: Full report knowledge structure
            max_sections_per_slide: Maximum number of relevant sections to include per slide
        
        Returns:
            Dict mapping slide_number -> list of relevant report sections
        """
        slides = outline.get("slides", [])
        all_sections = report_knowledge.get("sections", [])
        
        if not all_sections:
            return {}
        
        slide_to_sections = {}
        
        for slide in slides:
            slide_num = slide.get("slide_number")
            if not slide_num:
                continue
            
            # Extract slide content for matching
            slide_title = slide.get("title", "").lower()
            key_points = [p.lower() for p in slide.get("key_points", [])]
            content_notes = slide.get("content_notes", "").lower()
            
            # Combine all slide text for matching
            slide_text = f"{slide_title} {' '.join(key_points)} {content_notes}"
            
            # Find relevant sections using keyword matching
            relevant = []
            for section in all_sections:
                section_id = section.get("id", "")
                section_label = section.get("label", "").lower()
                section_summary = section.get("summary", "").lower()
                section_key_points = [p.lower() for p in section.get("key_points", [])]
                
                # Calculate relevance score
                score = 0
                
                # Match section label with slide title (strong match)
                if section_label:
                    label_words = set(section_label.split())
                    slide_words = set(slide_title.split())
                    common_words = label_words.intersection(slide_words)
                    if common_words:
                        # More common words = higher score
                        score += len(common_words) * 3
                
                # Match section summary with slide content (medium match)
                if section_summary:
                    summary_words = set(section_summary.split()[:20])  # First 20 words
                    slide_words = set(slide_text.split())
                    common_words = summary_words.intersection(slide_words)
                    if common_words:
                        score += len(common_words) * 2
                
                # Match section key points with slide key points (strong match)
                # Refactored: Use itertools.product to avoid nested loops
                for section_kp, slide_kp in product(section_key_points, key_points):
                    section_kp_words = set(section_kp.split()[:5])  # First 5 words
                    slide_kp_words = set(slide_kp.split()[:5])
                    common_words = section_kp_words.intersection(slide_kp_words)
                    if common_words:
                        score += len(common_words) * 2
                
                # Match section label in content_notes (medium match)
                if section_label and section_label in content_notes:
                    score += 2
                
                # If score > 0, section is relevant
                if score > 0:
                    relevant.append((score, section))
            
            # Sort by relevance score (descending) and take top N
            relevant.sort(reverse=True, key=lambda x: x[0])
            slide_to_sections[slide_num] = [s[1] for s in relevant[:max_sections_per_slide]]
        
        return slide_to_sections
    
    @staticmethod
    def build_selective_context(
        outline: Dict,
        report_knowledge: Dict
    ) -> Dict:
        """
        Build minimal report_knowledge context with only relevant sections for slide generation.
        
        LESS AGGRESSIVE: For small reports (< 10 sections), includes all sections.
        For larger reports, includes relevant sections + ensures at least 70% coverage.
        
        Args:
            outline: Presentation outline with slides
            report_knowledge: Full report knowledge structure
        
        Returns:
            Minimal report_knowledge dict with relevant sections (less aggressive filtering)
        """
        all_sections = report_knowledge.get("sections", [])
        total_sections = len(all_sections)
        
        # LESS AGGRESSIVE: If report has few sections (< 10), include ALL sections
        # This prevents information loss and ensures agent has enough context
        if total_sections <= 10:
            logger.info(f"📊 Small report ({total_sections} sections): Including ALL sections (less aggressive filtering)")
            minimal_context = report_knowledge.copy()  # Use full context for small reports
            return minimal_context
        
        # For larger reports, use selective extraction but ensure minimum coverage
        # Always include metadata (small, essential)
        minimal_context = {
            "scenario": report_knowledge.get("scenario"),
            "duration": report_knowledge.get("duration"),
            "report_url": report_knowledge.get("report_url"),
            "report_title": report_knowledge.get("report_title"),
            "one_sentence_summary": report_knowledge.get("one_sentence_summary"),
            "audience_profile": report_knowledge.get("audience_profile"),
            "presentation_focus": report_knowledge.get("presentation_focus"),
            "key_takeaways": report_knowledge.get("key_takeaways", []),  # Include all, not just top 5
            "recommended_focus_for_presentation": report_knowledge.get("recommended_focus_for_presentation", [])
        }
        
        # Extract relevant sections for all slides (union of all relevant sections)
        slide_to_sections = ContextBuilder.extract_relevant_report_sections(outline, report_knowledge, max_sections_per_slide=5)
        
        # Collect all unique relevant sections (deduplicated by section ID)
        # Refactored: Use itertools.chain to flatten nested lists, then deduplicate
        seen_section_ids = set()
        relevant_sections = []
        
        for section in chain.from_iterable(slide_to_sections.values()):
            section_id = section.get("id")
            if section_id and section_id not in seen_section_ids:
                relevant_sections.append(section)
                seen_section_ids.add(section_id)
        
        # LESS AGGRESSIVE: Ensure minimum 70% coverage to prevent information loss
        min_coverage = max(7, int(total_sections * 0.7))  # At least 70% or minimum 7 sections
        if len(relevant_sections) < min_coverage:
            logger.warning(f"⚠️  Only {len(relevant_sections)} relevant sections found (need {min_coverage} for 70% coverage). Including all sections as fallback.")
            relevant_sections = all_sections
        else:
            logger.info(f"✅ Extracted {len(relevant_sections)} relevant sections (from {total_sections} total, {len(relevant_sections)/total_sections*100:.1f}% coverage)")
        
        minimal_context["sections"] = relevant_sections
        
        # Include all figures (usually small, and may be referenced by any slide)
        minimal_context["figures"] = report_knowledge.get("figures", [])
        
        return minimal_context

