'use client';

import { Cpu, Database, Network, ArrowRight } from 'lucide-react';
import { motion } from 'framer-motion';

export default function Extra() {
    const openArticleAt = (page: number) => {
        const event = new CustomEvent('open-article', { detail: { page } });
        window.dispatchEvent(event);
    };

    const specs = [
        {
            icon: <Database />,
            title: "TrackSys DB",
            desc: "Context-aware resolution of 427+ interconnected tables.",
            page: 2,
            color: "blue"
        },
        {
            icon: <Cpu />,
            title: "MCP Bridge",
            desc: "Production-grade tool-calling for LLM agents.",
            page: 4,
            color: "green"
        },
        {
            icon: <Network />,
            title: "Secure Tunnel",
            desc: "Encrypted transit—no raw SQL exposure to the LLM.",
            page: 9,
            color: "purple"
        }
    ];

    return (
        <section id="extra" className="py-16 sm:py-32 px-4 sm:px-6 bg-[#080808]">
            <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-20 items-center">
                <div className="space-y-4 sm:space-y-6">
                    <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold text-white mb-6 sm:mb-8 tracking-tight text-left italic">
                        Technical Infrastructure
                    </h2>

                    <div className="grid grid-cols-1 gap-4 sm:gap-6">
                        {specs.map((s, i) => (
                            <motion.div
                                key={i}
                                whileHover={{ scale: 1.01, x: 5 }}
                                whileTap={{ scale: 0.98 }}
                                onClick={() => openArticleAt(s.page)}
                                className="group relative flex gap-3 sm:gap-5 p-4 sm:p-6 rounded-2xl bg-white/5 border border-white/10 cursor-pointer overflow-hidden transition-all hover:border-blue-500/50 hover:bg-blue-500/5"
                            >
                                <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

                                <div className="text-blue-500 bg-blue-500/10 p-2 sm:p-3 rounded-lg h-fit group-hover:bg-blue-500 group-hover:text-white transition-colors">
                                    <div className="w-5 h-5 sm:w-6 sm:h-6">{s.icon}</div>
                                </div>

                                <div className="flex-1">
                                    <h5 className="text-white font-bold text-base sm:text-lg mb-0.5 sm:mb-1 flex items-center gap-2 flex-wrap">
                                        {s.title}
                                        <ArrowRight size={12} className="sm:w-[14px] sm:h-[14px] opacity-0 group-hover:opacity-100 -translate-x-1 sm:-translate-x-2 group-hover:translate-x-0 transition-all" />
                                    </h5>
                                    <p className="text-xs sm:text-sm text-gray-400 leading-relaxed">{s.desc}</p>
                                </div>

                                <div className="absolute top-2 right-2 sm:top-4 sm:right-4 text-[8px] sm:text-[10px] font-mono text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity uppercase tracking-widest">
                                    View Protocol_Log
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </div>

                {/* Animated Status Circle - Responsive */}
                <div className="relative aspect-square flex items-center justify-center mt-8 lg:mt-0">
                    <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
                        className="absolute inset-0 rounded-full border-2 border-dashed border-blue-500/20"
                    />
                    <div className="w-3/4 h-3/4 bg-[#0a0a0a] rounded-full border border-blue-500/40 flex flex-col items-center justify-center p-4 sm:p-8 text-center shadow-[0_0_50px_rgba(59,130,246,0.1)]">
                        <div className="font-mono text-[8px] sm:text-[10px] space-y-2 sm:space-y-3">
                            <p className="text-blue-500 animate-pulse font-bold tracking-[0.1em] sm:tracking-[0.2em]">
                                // SYSTEM_STATUS: OPERATIONAL
                            </p>
                            <div className="py-1 sm:py-2 px-2 sm:px-4 bg-white/5 rounded border border-white/10">
                                <p className="text-gray-500 text-[8px] sm:text-[10px]">MCP_ENDPOINT: <span className="text-white text-[8px] sm:text-[10px]">mcp://tracksys.local</span></p>
                                <p className="text-gray-500 text-[8px] sm:text-[10px]">SYNC_SPEED: <span className="text-green-500">12ms</span></p>
                                <p className="text-gray-500 text-[8px] sm:text-[10px]">TABLE_MAP: <span className="text-blue-400">427_RESOLVED</span></p>
                            </div>
                            <div className="mt-2 sm:mt-4 flex gap-1 justify-center items-end h-6 sm:h-8">
                                {[1,2,3,4,5,6].map(i => (
                                    <motion.div
                                        key={i}
                                        animate={{ height: [8, 20, 12, 18, 8] }}
                                        transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.1 }}
                                        className="w-1 sm:w-1.5 bg-blue-600 rounded-full shadow-[0_0_10px_rgba(37,99,235,0.5)]"
                                    />
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}