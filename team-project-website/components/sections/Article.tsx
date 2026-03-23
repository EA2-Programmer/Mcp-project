'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FileText, X, Download, Maximize2 } from 'lucide-react';

export default function Articles() {
    const [isOpen, setIsOpen] = useState(false);

    // Link to your actual PDF file in the public folder
    const pdfUrl = "";

    return (
        <section id="articles" className="py-32 px-6 flex flex-col items-center">
            <div className="max-w-4xl w-full text-center mb-12">
                <h2 className="text-sm font-mono text-blue-500 tracking-[0.5em] uppercase mb-4">Documentation_Log</h2>
                <h3 className="text-4xl font-bold text-white tracking-tight">Technical Whitepaper</h3>
            </div>

            {/* --- THE THUMBNAIL / PREVIEW --- */}
            <motion.div
                layoutId="article-card"
                onClick={() => setIsOpen(true)}
                className="group relative cursor-pointer w-full max-w-2xl aspect-[3/4] md:aspect-[16/9] bg-[#0d0d0d] border border-white/10 rounded-xl overflow-hidden shadow-2xl transition-all hover:border-blue-500/50"
            >
                {/* Background Decor: Makes it look like a document is inside */}
                <div className="absolute inset-0 bg-gradient-to-b from-white/[0.02] to-transparent" />

                <div className="absolute inset-0 flex flex-col items-center justify-center p-12 text-center">
                    <FileText size={64} className="text-blue-600 mb-6 group-hover:scale-110 transition-transform duration-500" />
                    <h4 className="text-2xl font-bold text-white mb-2 tracking-tight">TrackSys MCP Protocol Specification</h4>
                    <p className="text-gray-500 font-mono text-xs uppercase tracking-widest mb-8">PDF DOCUMENT // 12 PAGES</p>

                    <div className="flex items-center gap-2 text-blue-400 font-semibold group-hover:text-blue-300 transition-colors">
                        <Maximize2 size={18} />
                        <span>Click to Expand & Read</span>
                    </div>
                </div>

                {/* Subtle corner fold effect */}
                <div className="absolute top-0 right-0 w-16 h-16 bg-white/5 border-b border-l border-white/10 -translate-y-8 translate-x-8 rotate-45 group-hover:translate-y-0 group-hover:translate-x-0 transition-all duration-500" />
            </motion.div>

            {/* --- THE FULL-SCREEN ZOOM OVERLAY --- */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-[100] bg-black/95 backdrop-blur-md flex flex-col items-center justify-start pt-20 pb-10 px-4"
                    >
                        {/* Control Bar */}
                        <div className="max-w-5xl w-full flex items-center justify-between mb-6 px-4">
                            <h4 className="text-white font-bold truncate">Technical_Specification_v1.0.pdf</h4>
                            <div className="flex gap-4">
                                <a href={pdfUrl} download className="p-2 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 transition text-gray-300">
                                    <Download size={20} />
                                </a>
                                <button
                                    onClick={() => setIsOpen(false)}
                                    className="p-2 bg-blue-600 rounded-lg hover:bg-blue-500 transition text-white"
                                >
                                    <X size={20} />
                                </button>
                            </div>
                        </div>

                        {/* Scrollable PDF Container */}
                        <motion.div
                            layoutId="article-card"
                            className="w-full max-w-5xl h-full bg-white rounded-t-lg overflow-y-auto shadow-2xl custom-scrollbar"
                        >
                            {/* If you want to use a real PDF viewer, use an iframe: */}
                            <iframe
                                src={`${pdfUrl}#view=FitH`}
                                className="w-full h-full border-none"
                                title="Documentation Viewer"
                            />
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </section>
    );
}