# Integration Project: PowerToChoose MCP ↔ Capstone Agent
**Date Started:** December 28, 2025  
**Goal:** Replace Google Search in Kaggle Capstone Project with PowerToChoose MCP Server

---

## 📋 Running Log

### Session 1: Initial Assessment (Dec 28, 2025)

#### Discovery Phase
- ✅ Located capstone project: `c:\code\kaggle-genai-agent-capstone-project\`
- ✅ Reviewed capstone architecture documents
- ✅ Identified current implementation uses Google Search for plan discovery

#### Capstone Project Current State
**Project Name:** Smart Meter Power Plan Finder  
**Framework:** Google Agent Development Kit (ADK)  
**Model:** Gemini 2.0 Flash Experimental

**Current Architecture:**
```
Power Plan Finder Agent (Orchestrator)
├── Meter Analysis Tool (FunctionTool)
│   └── Analyzes smart meter CSV data
└── Search Agent (AgentTool - A2A)
    └── GoogleSearchTool ← REPLACE THIS
        └── Searches web for Texas electricity plans
```

**Key Components:**
1. **Power Plan Finder Agent** - Main orchestrator
2. **Search Agent** - Uses GoogleSearchTool to find plans
3. **Meter Analysis Tool** - Processes smart meter data (5 household types)

**Data Flow:**
1. User provides meter ID (or random selection)
2. Meter tool fetches & analyzes CSV (2,190 records → 500 token summary)
3. Search Agent queries Google for plans
4. Power Plan Agent calculates costs & recommends 2-3 plans

#### PowerToChoose MCP Server Current State
**Location:** `c:\code\powertochoose-mcp\`  
**Status:** ✅ Fully functional with real data

**Available Tools:**
1. **`search_plans`** - Search by ZIP code with optional filters
   - Parameters: `zip_code`, `classifications[]`, `max_results`
   - Returns: Structured plan data with costs at 500/1000/2000 kWh
   
2. **`calculate_plan_cost`** - Detailed cost breakdown
   - Parameters: `plan_id`
   - Returns: Full cost analysis at 3 usage tiers

**Current Data:**
- 163 real plans scraped from ZIP 75074 (Plano, TX)
- API-based scraper (reliable, no HTML parsing)
- SQLite database with complete rate structures
- Classifications: green, 100_renewable, fixed_rate, time_of_use, etc.

---

## 🎯 Integration Plan (DRAFT)

### Phase 1: Assessment & Planning
- [ ] **Q1 to User:** Review the notebook to understand exact Google Search usage
- [ ] **Q2 to User:** Clarify ZIP code handling (capstone may need multiple TX ZIPs)
- [ ] **Q3 to User:** Confirm if we keep dual approach (search agent + MCP) or replace entirely
- [ ] Map meter analysis outputs to MCP search parameters

### Phase 2: MCP Tool Integration
- [ ] Update requirements.txt to include MCP dependencies
- [ ] Create MCP client/tool wrapper for ADK framework
- [ ] Replace GoogleSearchTool with PowerToChooseTool
- [ ] Update Search Agent instructions

### Phase 3: Data Mapping & Enhancement
- [ ] Map household usage patterns to plan classifications
- [ ] Enhance cost calculation with actual meter data
- [ ] Update recommendation logic to use MCP plan data

### Phase 4: Testing & Validation
- [ ] Test with all 5 household types
- [ ] Verify cost calculations match expectations
- [ ] Compare recommendations quality (Google vs MCP)

### Phase 5: Documentation
- [ ] Update capstone writeup
- [ ] Document new architecture
- [ ] Create demo notebook

---

## ❓ Clarification Questions

### Question 1 (PENDING USER RESPONSE):
**Need to examine the notebook:** Can you share or open the `powerplanfinder.ipynb` file so I can see:
- How GoogleSearchTool is currently configured
- What search queries are being sent
- How search results are parsed and used
- The exact integration point where we'll replace the search agent

**Context:** The README mentions the notebook contains the complete implementation, but I need to see the actual code to understand the integration points.

---

## 📝 Notes & Decisions
- Capstone uses **multi-agent A2A pattern** (Agent-to-Agent communication)
- Pre-summarization reduces 50K tokens to 500 tokens
- Target: 2-3 plan recommendations with cost estimates
- MCP server already returns structured data - perfect fit!

---

## 🚧 Blockers & Risks
None identified yet - awaiting notebook review

---

## 📊 Success Criteria
1. ✅ Replace Google Search with MCP server
2. ✅ Maintain or improve recommendation quality
3. ✅ Keep pre-summarization pattern efficiency
4. ✅ Work with all 5 household types
5. ✅ Provide accurate cost calculations
6. ✅ Update all documentation

---

*Last Updated: Dec 28, 2025*
