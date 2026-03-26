'use client';

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Download, Maximize2, FileText } from 'lucide-react';
import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';

export default function Articles() {
    const [isOpen, setIsOpen] = useState(false);
    const [isDownloading, setIsDownloading] = useState(false);
    const contentRef = useRef<HTMLDivElement>(null);

    // Deep linking from Extra.tsx
    useEffect(() => {
        const handleExternalOpen = (e: any) => {
            const pageNumber = e.detail?.page;
            if (!pageNumber) return;

            setIsOpen(true);

            setTimeout(() => {
                const pages = document.querySelectorAll('.document-page');
                if (pages[pageNumber - 1]) {
                    pages[pageNumber - 1].scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }, 900);
        };

        window.addEventListener('open-article', handleExternalOpen);
        return () => window.removeEventListener('open-article', handleExternalOpen);
    }, []);

    const generatePDF = async () => {
        if (!contentRef.current) {
            console.error('Content ref is null');
            return;
        }

        setIsDownloading(true);

        try {
            const element = contentRef.current;
            let pages = Array.from(element.querySelectorAll('.document-page')) as HTMLElement[];

            if (pages.length === 0) {
                throw new Error('No pages found to generate PDF');
            }

            const pdf = new jsPDF('p', 'mm', 'a4');
            const pageWidth = pdf.internal.pageSize.getWidth();

            await new Promise(resolve => setTimeout(resolve, 600));

            pages = Array.from(element.querySelectorAll('.document-page')) as HTMLElement[];

            for (let i = 0; i < pages.length; i++) {
                const page = pages[i];

                const images = page.querySelectorAll('img');
                await Promise.all(
                    Array.from(images).map((img) => {
                        if (img.complete && img.naturalHeight !== 0) return Promise.resolve();
                        return new Promise<void>((resolve) => {
                            const onLoadOrError = () => resolve();
                            img.onload = onLoadOrError;
                            img.onerror = onLoadOrError;
                            if (!img.complete) img.src = img.src;
                        });
                    })
                );

                await new Promise(resolve => setTimeout(resolve, 200));

                const canvas = await html2canvas(page, {
                    scale: 2,
                    backgroundColor: '#ffffff',
                    logging: false,
                    useCORS: true,
                    allowTaint: true,
                    width: Math.max(page.scrollWidth, 900),
                    height: page.scrollHeight,
                    removeContainer: true,
                    onclone: (clonedDoc, clonedElement) => {
                        const clonedPages = clonedDoc.querySelectorAll('.document-page');
                        clonedPages.forEach((clonedPage: Element) => {
                            const footer = clonedPage.querySelector('.page-footer') as HTMLElement;
                            if (footer) {
                                footer.style.position = 'absolute';
                                footer.style.bottom = '45px';
                                footer.style.left = '80px';
                                footer.style.right = '80px';
                                footer.style.width = 'auto';
                            }
                        });

                        if (clonedElement instanceof HTMLElement) {
                            clonedElement.style.visibility = 'visible';
                            clonedElement.style.opacity = '1';
                            clonedElement.style.display = 'block';
                            clonedElement.style.position = 'relative';
                        }
                    }
                });

                const imgData = canvas.toDataURL('image/png', 1.0);
                const imgWidth = pageWidth;
                const imgHeight = (canvas.height * pageWidth) / canvas.width;

                if (i > 0) {
                    pdf.addPage();
                }

                pdf.addImage(imgData, 'PNG', 0, 0, imgWidth, imgHeight, undefined, 'FAST');
            }

            pdf.save('The_TrakSYS_Paradox_Whitepaper.pdf');
        } catch (error) {
            console.error('Error generating PDF:', error);
            alert('PDF generation failed. Please check the console for details and try again.');
        } finally {
            setIsDownloading(false);
        }
    };

    const articleContent = `
        <style>
            .pdf-viewer {
                background: #525659;
                padding: 24px 16px;
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 20px;
                min-height: 100vh;
            }
            
            .document-page {
                background: white;
                width: 100%;
                max-width: 900px;
                padding: 40px 24px 100px 24px;
                color: #1a1a1a;
                font-family: 'Georgia', 'Times New Roman', Times, serif;
                position: relative;
                border-radius: 8px;
                box-shadow: 0 8px 24px rgba(0,0,0,0.2);
                box-sizing: border-box;
            }
            
            .document-page h1 {
                font-size: clamp(1.8rem, 5vw, 2.5rem);
                font-weight: 700;
                margin-top: 0;
                margin-bottom: 1rem;
                line-height: 1.2;
                color: #000;
            }
            
            .document-page h2 {
                font-size: clamp(1.4rem, 4vw, 1.75rem);
                font-weight: 600;
                margin-top: 1.5rem;
                margin-bottom: 0.75rem;
                padding-bottom: 0.5rem;
                border-bottom: 2px solid #e5e5e5;
                color: #000;
            }
            
            .document-page h3 {
                font-size: clamp(1.1rem, 3.5vw, 1.25rem);
                font-weight: 600;
                margin-top: 1.25rem;
                margin-bottom: 0.5rem;
                color: #111;
            }
            
            .document-page p {
                font-size: clamp(0.9rem, 3vw, 1rem);
                margin-bottom: 0.85rem;
                line-height: 1.6;
                color: #333;
            }
            
            .document-page ul, .document-page ol {
                margin-bottom: 0.85rem;
                padding-left: 1.5rem;
            }
            
            .document-page li {
                font-size: clamp(0.9rem, 3vw, 1rem);
                margin-bottom: 0.4rem;
                line-height: 1.6;
            }
            
            .document-page code {
                font-family: 'SF Mono', 'Courier New', monospace;
                background: #f4f4f4;
                padding: 0.15rem 0.35rem;
                border-radius: 4px;
                font-size: 0.85em;
                word-break: break-word;
            }
            
            .document-page pre {
                font-family: 'SF Mono', 'Courier New', monospace;
                background: #1e1e1e;
                color: #d4d4d4;
                padding: 0.85rem;
                border-radius: 8px;
                overflow-x: auto;
                margin-bottom: 0.85rem;
                font-size: 0.8rem;
            }
            
            .document-page blockquote {
                font-family: 'Georgia', 'Times New Roman', Times, serif;
                border-left: 4px solid #3b82f6;
                padding-left: 0.85rem;
                margin: 0.85rem 0;
                color: #555;
                font-style: italic;
            }
            
            .document-page img {
                max-width: 100%;
                height: auto;
                border-radius: 8px;
                margin: 0.85rem 0;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                border: 1px solid #e5e7eb;
                display: block;
            }
            
            .page-footer {
                font-family: 'SF Mono', 'Courier New', monospace;
                position: absolute;
                bottom: 24px;
                left: 24px;
                right: 24px;
                text-align: center;
                font-size: 10px;
                color: #9ca3af;
                border-top: 1px solid #e5e7eb;
                padding-top: 10px;
                background: white;
            }
            
            hr {
                margin: 1.5rem 0;
                border: none;
                border-top: 1px solid #e5e7eb;
            }
            
            a {
                color: #3b82f6;
                text-decoration: none;
                word-break: break-all;
            }
            
            a:hover {
                text-decoration: underline;
            }
            
            @media (min-width: 768px) {
                .pdf-viewer {
                    padding: 48px 0;
                    gap: 24px;
                }
                .document-page {
                    padding: 72px 80px 120px 80px;
                    border-radius: 2px;
                }
                .document-page h1 {
                    margin-bottom: 1.5rem;
                }
                .document-page p {
                    margin-bottom: 1rem;
                }
                .page-footer {
                    bottom: 36px;
                    left: 80px;
                    right: 80px;
                    font-size: 11px;
                }
            }
        </style>
        
        <div class="pdf-viewer">
            <!-- PAGE 1 -->
            <div class="document-page">
                <h1>The TrakSYS Paradox: How We Used MCP to Bridge the Gap Between Raw Data and Real Answers</h1>
                
                <p><strong>Research question:</strong> How can we enable non-technical factory staff to query complex manufacturing data using natural language, while ensuring accuracy and contextual understanding?</p>
                
                <p>You know what's insane? AI is out here doing predictive maintenance, generative design, quality control—all this futuristic stuff. But ask a factory supervisor a simple question like "Why did the line stop yesterday?" and suddenly we're back in the dark ages. They can't get an answer. Not because the data isn't there—oh, it's definitely there—but because nobody can actually talk to it.</p>
                
                <p>Here's the reality. Companies invest millions in data collection. Sensors everywhere, systems tracking every movement, every batch, every second. But for the people who actually need that data to make decisions? It might as well be invisible.</p>
                
                <p>Take AG Solution. Global industrial automation leader. Big name. Their plants generate terabytes of production data through TrakSYS—a Manufacturing Execution System tracking every order, batch, and equipment event in real time. Sounds impressive, right? It is. But ask a floor supervisor a simple question like "Why did yesterday's shift have so much downtime?" and watch what happens. They submit a ticket. Wait hours. Get a spreadsheet. Maybe. If they're lucky.</p>
                
                <p>Why? Because making sense of that data requires SQL expertise and deep knowledge of complex database relationships. Technical skills that operational staff—you know, the people actually running the factory—simply don't have time to master in the heat of a production cycle.</p>
                
                <p>So here's the question that got us thinking: What if that gap just... didn't exist? What if a shift supervisor could ask a question in plain English and get an immediate, accurate answer without needing to become a database expert?</p>
                
                <p>That's exactly what we set out to build. This article walks you through how we used the Model Context Protocol (MCP) to create an AI assistant that bridges the gap between everyday language and industrial data. We'll show you the architecture, the tools we built, and how it all comes together to let anyone ask questions and get real answers—without exposing sensitive company data or breaking anything. Let's dive in.</p>
                
                <div class="page-footer">1 / 12</div>
            </div>
            
            <!-- PAGE 2 -->
            <div class="document-page">
                <h2>Understanding the Data Landscape: More Than Just Tables</h2>
                
                <p>So after establishing why this problem matters, guess what our first task was? Yep—actually building the MCP server that would solve it. Which meant we had to get up close and personal with a system that, six weeks ago, I'd never even heard of: a Manufacturing Execution System, or MES.</p>
                
                <p>Now, I know some of you are gonna be wondering what that is—or maybe some of us already know—but for those who don't know or didn't know like me six weeks ago? It's basically a system that monitors, tracks, documents, and controls the process of manufacturing goods from raw materials to finished products. Yeah, you heard that right, an "MES".</p>
                
                <p>So with that out the way, let me explain the data structure of the MES we worked with. TrakSYS—which is the MES we used—basically tracks production at a granular level. And its data model? It's built around four main layers.</p>
                
                <p><strong>First</strong>, production orders are stored in a table called <code>tJob</code>. Weird, right? I thought it'd be named <code>tProduct</code> or something, but nope. This table basically represents a production order or work order from the ERP system. So it contains things like <code>productID</code> and <code>plannedStart</code>—basically when you should start, or I suppose when production would start.</p>
                
                <p><strong>Second</strong>, batches. But not the kind you bake! Batches are the physical execution of a job. So while the production table defines what needs to be done from the ERP, the batches show what is currently happening or has already happened. Each batch can be seen as a real, trackable instance of production where materials are processed, machines are involved, and actual output is generated.</p>
                
                <p><strong>Third</strong>, events. These are the heartbeat of the factory—the specific activities that happen during a batch. For the data engineers in the room, you know the drill: this data isn't in one neat pile. It's distributed across several specialized tables:</p>
                
                <ul>
                    <li><code>tBatchStep</code> — stores every process step executed with start/end times</li>
                    <li><code>tBatchParameter</code> — stores real-time readings like temperature, filling weight, pressure, etc., with min/max limits</li>
                    <li><code>tMaterialUseActual</code> — stores actual raw materials consumed, linked via <code>jobID</code></li>
                    <li><code>DBR</code> — stores free-text operator remarks and notes</li>
                    <li><code>tTask</code> — stores mandatory compliance quality tasks and their pass/fail status</li>
                </ul>
                
                <div class="page-footer">2 / 12</div>
            </div>
            
            <!-- PAGE 3 -->
            <div class="document-page">
                <p>Alright, so that's the structure. But here's where things get spicy.</p>
                
                <p>The biggest challenge—and I mean biggest—when working with an MES system is that even something as simple or easy as downtime? It's gonna be difficult. Because everything is spread across 50+ interconnected tables with foreign keys that don't actually have constraints. What I mean is: yeah, an ID can be a foreign key in another table, but there's no formal foreign key constraint tying them together. You'll always have to join multiple tables to get a complete picture of what you're looking for.</p>
                
                <p>This poses another question—or rather, more of a curiosity—like, how is database access alone able to solve this? Or is raw database access not enough for an AI to solve this?</p>
                
                <p>The answer is no. When you just send this to ChatGPT or other LLMs—and I can already hear some of you saying "but that's what prompts are for"—the thing is, yes and no.</p>
                
                <p>When an AI looks at raw SQL, it just sees column names and numbers. That's not enough context. I mean, imagine asking: what is a job? Or what does a batch actually mean? All of this can't be understood by prompt alone. Which is why the AI or LLM needs to know the exact table relationships to be able to answer your question.</p>
                
                <p>So if raw database access isn't the answer, what is? Let me show you what we built instead—and honestly, this is where things get really cool.</p>
                
                <div class="page-footer">3 / 12</div>
            </div>
            
            <!-- PAGE 4 -->
            <div class="document-page">
                <h2>The MCP Architecture: A Clean Bridge Between AI and the Factory</h2>
                
                <p>Okay, so now we'll look into the MCP architecture, which I think is the most significant technical innovation in this project. It's just a clean, production-grade bridge between an LLM and an MES database.</p>
                
                <img src="/images/Article/Architecture.png" alt="MCP Architecture Diagram">
                
                <p>The MCP architecture as seen in the above image isn't complex to understand—at least at an architectural level. But let me break down what we actually built.</p>
                
                <p>For our implementation, we built three distinct layers:</p>
                
                <h3>Data Queries Layer</h3>
                <p>This layer contains pure, reusable, highly optimized SQL functions with:</p>
                <ul>
                    <li>Automatic batch_name → batch_id → job_id resolution (because who wants to do that manually?)</li>
                    <li>Intelligent time-window fallback via DataAvailabilityCache</li>
                    <li>Deviation detection, planned vs. actual BOM aggregation (in Python)</li>
                    <li>All queries are parameterized and read-only (safety first, people)</li>
                </ul>
                
                <div class="page-footer">4 / 12</div>
            </div>
            
            <!-- PAGE 5 -->
            <div class="document-page">
                <h3>API Tools Layer</h3>
                <p>Each tool is defined using:</p>
                <ul>
                    <li><code>@mcp.tool()</code> decorator</li>
                    <li>Rich, LLM-friendly descriptions</li>
                    <li>Pydantic input_model (strict validation + field descriptions)</li>
                    <li>ToolResponse wrapper (success / partial / no_data / error)</li>
                </ul>
                
                <h3>Contextual Information Output Layer</h3>
                <p>This is the secret sauce.</p>
                <p>Every tool returns not just raw data, but:</p>
                <ul>
                    <li>methodology block (how the answer was derived)</li>
                    <li>time_info with fallback explanation</li>
                    <li>Business-level signals (is_deviation, total_quality_signals, compliance_rate_pct, etc.)</li>
                    <li>Actionable suggestions</li>
                </ul>
                
                <p>Now, when we look at all this—MCP, LLM, all that—it must've sparked some curiosity. I mean, I'm pretty sure some people are wondering: okay, what makes MCP so good beyond just seeing the architecture? How does it fair against traditional methods? And why do I think this is something everyone needs to try or hop on?</p>
                
                <div class="page-footer">5 / 12</div>
            </div>
            
            <!-- PAGE 6 -->
            <div class="document-page">
                <p>Let me break it down.</p>
                
                <p><strong>Raw SQL</strong> is basically useless here. The AI gets little to no business context—it just sees table names and numbers. And let's not talk about maintainability, because that's an absolute nightmare. Zero natural language support.</p>
                
                <p><strong>Traditional REST APIs</strong> are better on maintainability, sure. But they still have very limited natural language support and low business context. They treat every request as independent, which isn't how conversations work.</p>
                
                <p><strong>MCP</strong>, compared to both, excels in every aspect. AI understanding? You give it an incredible amount of business context. Maintainability? Excellent. Natural language support? Great.</p>
                
                <p>In summary, MCP gives the LLM first-class business tools instead of tables, while still giving developers full control and observability.</p>
                
                <img src="/images/Article/Tool%20Definition.png" alt="Tool Definition Example">
                
                <p>This clean separation—SQL abstraction → validated tool → contextual response—is what makes the entire system reliable, explainable, and truly LLM-native.</p>
                
                <p>Okay, I know we've read about enough about MCP right about now. But what if I told you that you haven't even seen the best part yet? At least for me.</p>
                
                <div class="page-footer">6 / 12</div>
            </div>
            
            <!-- PAGE 7 -->
            <div class="document-page">
                <h2>The Translation Layer: Turning Complexity into Simplicity</h2>
                
                <p>I can wholeheartedly say that my favorite part of this project is the translation layer. It literally turns 427 interconnected tables—like, damn, who could go through that? Definitely not me—where the connections are intertwined and sometimes vague, into clean, reliable, business-meaningful tools the LLM can actually use.</p>
                
                <h3>The Problem with Raw SQL is that it's Useless to an LLM</h3>
                
                <p>A single "simple" question like: "Show me material consumption for batch 456" requires joining at least four tables:</p>
                <ul>
                    <li><code>tBatch</code> → <code>tJob</code> (to find the JobID)</li>
                    <li><code>tMaterialUseActual</code> (via JobID)</li>
                    <li><code>tMaterial</code> (to get names and codes)</li>
                    <li>Optional <code>_SAPBOM</code> for planned quantities</li>
                </ul>
                
                <p>An LLM trying to write this SQL directly would fail 9 times out of 10. No joke.</p>
                
                <h3>The Solution: The Translation Layer</h3>
                <p>We built a clean abstraction that does three things:</p>
                <ul>
                    <li>Hides the complexity (SQL joins, name resolution, time fallbacks)</li>
                    <li>Enforces business rules (validation, aliases, safe limits)</li>
                    <li>Adds context (methodology, explanations, fallback messages)</li>
                </ul>
                
                <div class="page-footer">7 / 12</div>
            </div>
            
            <!-- PAGE 8 -->
            <div class="document-page">
                <h3>Real Example: Time Windows + Filters + Relationships</h3>
                <p>Here's how the <code>get_batch_materials</code> tool handles a natural question.</p>
                <p>If a user asks, for example: "Which materials were consumed for job 1187?"</p>
                
                <img src="/images/Article/get_batch_mat.png" alt="Code Example">
                
                <p>The LLM doesn't and won't ever see any of this. It just calls one clean tool. Beautiful, right?</p>
                
                <h3>Validation Strategies That Prevent Hallucination</h3>
                
                <p>To stop the LLM from guessing or hallucinating on manufacturing data, we built multiple layers of protection directly into the tools:</p>
                
                <ul>
                    <li><strong>Pydantic Input Models</strong> enforce strict type checking and required fields, while also providing rich, human-readable descriptions that guide the model on how to use each parameter correctly.</li>
                    <li><strong>Smart Alias Mapping</strong> automatically normalizes common user terms—for example, converting "Temperature" or "temp" into the exact database name "Temperature_batch," and "Filling Weight" into its proper variant—eliminating the most frequent cause of empty results.</li>
                    <li><strong>ToolResponse Wrapper</strong> ensures every answer follows a consistent structure (success, partial, no_data, or error) and never returns raw database rows without context or explanation.</li>
                    <li><strong>Methodology Field</strong> is included in every response so the LLM can see exactly how the data was retrieved, which tables were used, and what business rules were applied—removing any temptation to invent explanations.</li>
                    <li><strong>Unicode Cleanup</strong> fixes encoding issues that appear in some TrakSYS fields, decoding them cleanly before they reach the LLM.</li>
                </ul>
                
                <div class="page-footer">8 / 12</div>
            </div>
            
            <!-- PAGE 9 -->
            <div class="document-page">
                <p>Together, these layers turn a complex, error-prone database into a safe, reliable interface that the AI can trust.</p>
                
                <p>Alright, so we've got this powerful MCP server with all these carefully crafted tools. But a tool is useless without someone who knows how to use it, right? That's where the final piece comes in.</p>
                
                <h2>AI Agent Integration: From Raw Data to Expert Answers</h2>
                
                <p>And finally, the missing piece: our custom agent. This is the part that actually consumes the MCP tools we built. This is where it all happens. This is where raw data turns into expert-level manufacturing answers.</p>
                
                <h3>How the Agent Consumes MCP Tools</h3>
                
                <p>So here's how it works: the agent uses <strong>OpenAI Function Calling</strong>, where the LLM decides which tool(s) to call based on the user question. Those tools are made available through a <strong>Function Registry</strong> that dynamically converts every MCP tool into an OpenAI-compatible format with name, description, and parameters. When multiple tools need to be called, the agent handles them in <strong>Parallel Execution</strong> using <code>asyncio.gather</code> for speed. As answers come back, the agent delivers them through <strong>Streaming Response</strong> back to OpenWebUI in real time. And every result from the MCP server is wrapped in a <strong>ToolResponse Wrapper</strong> with status, methodology, time_info, and suggestions before being sent back to the LLM.</p>
                
                <p>What does all that mean? It means this architecture allows the agent to reason step-by-step, call tools in parallel, and explain its thinking exactly like a senior manufacturing engineer. Pretty cool, right?</p>
                
                <div class="page-footer">9 / 12</div>
            </div>
            
            <!-- PAGE 10 -->
            <div class="document-page">
                <h3>Demo Scenario: "Why did Line 3 stop yesterday?"</h3>
                
                <p>Let me show you what this actually looks like in action. Here's the real internal flow when a user asks that question:</p>
                
                <p><strong>User:</strong> "Why did Line 3 stop yesterday?"</p>
                
                <p><strong>Agent Orchestrator (Step-by-step reasoning):</strong></p>
                <ul>
                    <li>Calls <code>get_batches</code> with system_name="E3" + time_window="yesterday" → finds relevant batches</li>
                    <li>In parallel, calls <code>calculate_oee</code> for Line 3 on the same date → gets Availability %</li>
                    <li>Also calls <code>get_oee_downtime_events</code> for Line 3 → returns actual downtime events with fault codes and operator notes</li>
                    <li>Finally calls <code>get_batch_quality_analysis</code> on the affected batches → checks for parameter deviations and incomplete tasks</li>
                </ul>
                
                <p><strong>Final Answer (what the user sees):</strong></p>
                <blockquote>
                    "Line 3 stopped for 87 minutes yesterday (Availability = 68%).<br/>
                    Main causes:<br/>
                    - Equipment fault "E3-FAULT-12" from 09:14–10:41 (operator noted "conveyor jam")<br/>
                    - One incomplete compliance task (Weighing Checklist)<br/>
                    - No parameter deviations recorded.<br/>
                    This single event dropped the daily OEE by ~22 points."
                </blockquote>
                
                <img src="/images/Article/Line%20E2.png" alt="Demo Screenshot">
                <img src="/images/Article/OEE.png" alt="OEE Chart">
                
                <div class="page-footer">10 / 12</div>
            </div>
            
            <!-- PAGE 11 -->
            <div class="document-page">
                <p>See what happened there? The agent didn't guess—it used four tools in parallel and combined the results with business context. It's like having a manufacturing expert on call 24/7.</p>
                
                <h3>How We Ensured Expert-Level Accuracy</h3>
                
                <ul>
                    <li>Rich tool descriptions in the MCP layer guide the LLM on when and how to use each tool</li>
                    <li>Methodology field in every response explains exactly how the answer was calculated</li>
                    <li>Parallel tool calling prevents the agent from missing important signals</li>
                    <li>System prompt contains deep domain knowledge (product codes, material units, batch states, known data gaps, etc.)</li>
                    <li>Fallback handling is explicit—the agent always tells the user when it used fallback data</li>
                    <li>No raw SQL exposure—the LLM never sees table names or joins</li>
                </ul>
                
                <p>This combination turns a normal LLM into a true manufacturing expert that can diagnose issues, explain root causes, and suggest next actions with confidence.</p>
                
                <div class="page-footer">11 / 12</div>
            </div>
            
            <!-- PAGE 12 -->
            <div class="document-page">
                <h2>Conclusion</h2>
                
                <p>So after all that—the 427 tables, the complex joins, the translation layer, the custom agent—where did we land?</p>
                
                <p>Honestly? We built something pretty cool. Our MCP server and custom AI agent now let non-technical staff ask questions in plain English and get instant, accurate answers from TrakSYS data. Batches, events, KPIs—all of it. No tickets. No waiting. No SQL required.</p>
                
                <h3>What We Achieved</h3>
                <p>MCP gave us something raw SQL and REST APIs couldn't: validated tools with real business context. The agent runs parallel tool calls, explains its reasoning, and delivers expert-level analysis. That whole "Why did Line 3 stop?" example? That's not a demo—that's the actual system working.</p>
                
                <h3>What Almost Broke Us</h3>
                <p>Let me be real with you. We came from a world where databases had maybe 50 tables. Then we walked into 427 tables with no foreign key constraints. Yeah. We spent more time figuring out what the data meant than writing code. Because here's the thing—the MCP server and agent are only as good as the context you give them. And tracing relationships across a database that refuses to connect itself? That was the hardest part.</p>
                
                <h3>What We Learned</h3>
                <p>Not all LLMs are built the same. Some gave great answers. Some gave... creative ones. That's why we built our own agent with custom context. Also, traceability tools? Surprisingly lacking. We ended up building what we needed because nothing off the shelf fit our industrial requirements. And one more thing: data quality matters. Garbage in, garbage out—AI doesn't magically fix bad data.</p>
                
                <h3>What's Next</h3>
                <p>More tools. Better context handling. A UI that anyone can use without training. The foundation is there.</p>
                
                <h3>The Real Impact</h3>
                <p>Here's what this means: what used to take hours—tickets, waiting, spreadsheets—now takes seconds. A supervisor asks a question. The system answers. Decision made. Production keeps moving. That's not just efficiency. That's empowering the people who actually run the factory.</p>
                
                <h3>So Here's My Pitch</h3>
                <p>Whether you're in manufacturing or any industry dealing with complex data, give MCP a shot. It turns data into conversation. It turns "I don't know" into "here's exactly what happened." And honestly? It's just really satisfying to watch someone ask a question in plain English and get an expert-level answer back in seconds.</p>
                
                <p><strong>Try it out.</strong></p>
                
                <hr/>
                
                <h3>References</h3>
                <ul>
                    <li>AI in manufacturing: A comprehensive guide | SAP - <a href="https://www.sap.com/products/scm/digital-manufacturing/what-is-mes.html" target="_blank">https://www.sap.com/products/scm/digital-manufacturing/what-is-mes.html</a></li>
                    <li>What is the Model Context Protocol (MCP)? - Model Context Protocol</li>
                </ul>
                
                <div class="page-footer">12 / 12</div>
            </div>
        </div>
    `;

    return (
        <section id="articles" className="py-16 sm:py-32 px-4 sm:px-6 flex flex-col items-center">
            <div className="max-w-4xl w-full text-center mb-8 sm:mb-12">
                <h2 className="text-xs sm:text-sm font-mono text-blue-500 tracking-[0.5em] uppercase mb-3 sm:mb-4">Documentation_Log</h2>
                <h3 className="text-2xl sm:text-3xl md:text-4xl font-bold text-white tracking-tight">Technical Whitepaper</h3>
            </div>

            {/* THUMBNAIL CARD - Works on ALL devices (PC, tablet, mobile) */}
            <motion.div
                layoutId="article-card"
                onClick={() => setIsOpen(true)}
                onTouchStart={() => setIsOpen(true)}
                style={{ cursor: 'pointer' }}
                className="group relative w-full max-w-2xl aspect-[4/3] sm:aspect-[16/9] bg-[#0d0d0d] border border-white/10 rounded-xl overflow-hidden shadow-2xl transition-all hover:border-blue-500/50 active:scale-[0.98] hover:shadow-blue-500/20"
            >
                <div className="absolute inset-0 bg-gradient-to-b from-white/[0.02] to-transparent" />
                <div className="absolute inset-0 flex flex-col items-center justify-center p-6 sm:p-12 text-center">
                    <FileText size={40} className="sm:text-6xl text-blue-600 mb-4 sm:mb-6 group-hover:scale-110 transition-transform duration-500" />
                    <h4 className="text-xl sm:text-2xl font-bold text-white mb-1 sm:mb-2 tracking-tight">The TrakSYS Paradox</h4>
                    <p className="text-gray-500 font-mono text-[10px] sm:text-xs uppercase tracking-widest mb-4 sm:mb-8">TECHNICAL WHITEPAPER // 12 PAGES</p>
                    <div className="flex items-center gap-2 text-blue-400 font-semibold group-hover:text-blue-300 transition-colors text-sm sm:text-base">
                        <Maximize2 size={16} className="sm:w-[18px] sm:h-[18px]" />
                        <span>Click to Expand & Read</span>
                    </div>
                </div>
                <div className="absolute top-0 right-0 w-12 h-12 sm:w-16 sm:h-16 bg-white/5 border-b border-l border-white/10 -translate-y-6 sm:-translate-y-8 translate-x-6 sm:translate-x-8 rotate-45 group-hover:translate-y-0 group-hover:translate-x-0 transition-all duration-500" />
            </motion.div>

            {/* FULLSCREEN MODAL - Responsive */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-[100] bg-black/90 flex flex-col items-center overflow-hidden"
                    >
                        {/* CONTROL BAR - Responsive */}
                        <div className="w-full bg-[#2d2d2d] border-b border-white/10 py-2 sm:py-3 px-3 sm:px-6 flex items-center justify-between z-10 shadow-lg shrink-0">
                            <div className="flex items-center gap-2 sm:gap-3 text-white font-mono text-[10px] sm:text-sm">
                                <FileText size={14} className="sm:w-[18px] sm:h-[18px] text-blue-400" />
                                <span className="truncate max-w-[120px] sm:max-w-none">The_TrakSYS_Paradox_Whitepaper.pdf</span>
                            </div>
                            <div className="flex gap-2 sm:gap-3">
                                <button
                                    onClick={generatePDF}
                                    disabled={isDownloading}
                                    className={`flex items-center gap-1 sm:gap-2 px-2 sm:px-4 py-1 sm:py-1.5 rounded-md text-white text-[10px] sm:text-xs font-semibold transition ${
                                        isDownloading 
                                            ? 'bg-gray-500 cursor-not-allowed' 
                                            : 'bg-blue-600 hover:bg-blue-500'
                                    }`}
                                >
                                    <Download size={12} className="sm:w-[14px] sm:h-[14px]" />
                                    <span className="hidden sm:inline">{isDownloading ? 'GENERATING...' : 'DOWNLOAD PDF'}</span>
                                    <span className="sm:hidden">{isDownloading ? '...' : 'PDF'}</span>
                                </button>
                                <button
                                    onClick={() => setIsOpen(false)}
                                    className="p-1 sm:p-1.5 bg-red-600/80 rounded-md text-white hover:bg-red-500 transition"
                                >
                                    <X size={14} className="sm:w-[18px] sm:h-[18px]" />
                                </button>
                            </div>
                        </div>

                        {/* SCROLLABLE DOCUMENT AREA */}
                        <div className="w-full flex-1 overflow-y-auto">
                            <div ref={contentRef} dangerouslySetInnerHTML={{ __html: articleContent }} />
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </section>
    );
}