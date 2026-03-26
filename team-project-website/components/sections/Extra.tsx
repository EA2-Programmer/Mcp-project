'use client';

import { Cpu, Database, Network, ArrowRight } from 'lucide-react';
import { motion } from 'framer-motion';

export default function Extra() {
    // Function to trigger the article opening via a custom event
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
        <section id="extra" className="py-32 px-6 bg-[#080808]">
            <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-20 items-center">
                <div className="space-y-6">
                    <h2 className="text-4xl font-bold text-white mb-8 tracking-tight text-left italic">
                        Technical Infrastructure
                    </h2>

                    <div className="grid grid-cols-1 gap-6">
                        {specs.map((s, i) => (
                            <motion.div
                                key={i}
                                whileHover={{ scale: 1.02, x: 10 }}
                                whileTap={{ scale: 0.98 }}
                                onClick={() => openArticleAt(s.page)}
                                className="group relative flex gap-5 p-6 rounded-2xl bg-white/5 border border-white/10 cursor-pointer overflow-hidden transition-all hover:border-blue-500/50 hover:bg-blue-500/5"
                            >
                                {/* Animated Background Glow */}
                                <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

                                <div className="text-blue-500 bg-blue-500/10 p-3 rounded-lg h-fit group-hover:bg-blue-500 group-hover:text-white transition-colors">
                                    {s.icon}
                                </div>

                                <div className="flex-1">
                                    <h5 className="text-white font-bold text-lg mb-1 flex items-center gap-2">
                                        {s.title}
                                        <ArrowRight size={14} className="opacity-0 group-hover:opacity-100 -translate-x-2 group-hover:translate-x-0 transition-all" />
                                    </h5>
                                    <p className="text-sm text-gray-400 leading-relaxed">{s.desc}</p>
                                </div>

                                {/* "Click Bait" Badge */}
                                <div className="absolute top-4 right-4 text-[10px] font-mono text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity uppercase tracking-widest">
                                    View Protocol_Log
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </div>

                {/* Animated Status Circle */}
                <div className="relative aspect-square flex items-center justify-center">
                    <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
                        className="absolute inset-0 rounded-full border-2 border-dashed border-blue-500/20"
                    />
                    <div className="w-3/4 h-3/4 bg-[#0a0a0a] rounded-full border border-blue-500/40 flex flex-col items-center justify-center p-8 text-center shadow-[0_0_50px_rgba(59,130,246,0.1)]">
                        <div className="font-mono text-[10px] space-y-3">
                            <p className="text-blue-500 animate-pulse font-bold tracking-[0.2em]">
                                // SYSTEM_STATUS: OPERATIONAL
                            </p>
                            <div className="py-2 px-4 bg-white/5 rounded border border-white/10">
                                <p className="text-gray-500">MCP_ENDPOINT: <span className="text-white">mcp://tracksys.local</span></p>
                                <p className="text-gray-500">SYNC_SPEED: <span className="text-green-500">12ms</span></p>
                                <p className="text-gray-500">TABLE_MAP: <span className="text-blue-400">427_RESOLVED</span></p>
                            </div>
                            <div className="mt-4 flex gap-1.5 justify-center items-end h-8">
                                {[1,2,3,4,5,6].map(i => (
                                    <motion.div
                                        key={i}
                                        animate={{ height: [10, 32, 15, 25, 10] }}
                                        transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.1 }}
                                        className="w-1.5 bg-blue-600 rounded-full shadow-[0_0_10px_rgba(37,99,235,0.5)]"
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