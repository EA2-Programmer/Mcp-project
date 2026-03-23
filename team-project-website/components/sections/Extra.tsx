import { Cpu, Database, Network } from 'lucide-react';

export default function Extra() {
    const specs = [
        { icon: <Database />, title: "TrackSys DB", desc: "Native connection to MES telemetry." },
        { icon: <Cpu />, title: "MCP Bridge", desc: "Secure tool-calling for LLM agents." },
        { icon: <Network />, title: "Secure Tunnel", desc: "Encrypted industrial data transit." }
    ];

    return (
        <section id="extra" className="py-32 px-6 bg-[#080808]">
            <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-20 items-center">
                <div>
                    <h2 className="text-4xl font-bold text-white mb-6 tracking-tight text-left">Technical Infrastructure</h2>
                    <div className="grid grid-cols-1 gap-4">
                        {specs.map((s, i) => (
                            <div key={i} className="flex gap-4 p-4 rounded-xl bg-white/5 border border-white/10">
                                <div className="text-blue-500">{s.icon}</div>
                                <div><h5 className="text-white font-bold">{s.title}</h5><p className="text-sm text-gray-500">{s.desc}</p></div>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="relative aspect-square bg-blue-600/5 rounded-full border border-white/5 flex items-center justify-center">
                    <div className="w-3/4 h-3/4 bg-[#0a0a0a] rounded-full border border-blue-500/20 flex flex-col items-center justify-center p-8 text-center">
                        <div className="font-mono text-[10px] space-y-2">
                            <p className="text-blue-500 animate-pulse">// SYSTEM_STATUS: OPERATIONAL</p>
                            <p className="text-gray-500">MCP_ENDPOINT: <span className="text-white">mcp://tracksys.local</span></p>
                            <p className="text-gray-500">SYNC_SPEED: <span className="text-green-500">12ms</span></p>
                            <div className="mt-4 flex gap-1 justify-center">
                                {[1,2,3,4].map(i => <div key={i} className="w-1 h-4 bg-blue-600 animate-bounce" style={{animationDelay: `${i*0.2}s`}} />)}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}