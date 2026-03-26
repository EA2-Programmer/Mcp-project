import { Linkedin, Github, ExternalLink, ShieldCheck } from 'lucide-react';
const team = [
    { name: "Aisosa", role: "Systems Architect", li: "https://www.linkedin.com/in/aisosa-edobor-137041252/", gh: "#", img: "/images/Aisosa.jpeg" },
    { name: "Kingsley", role: "Protocol Lead", li: "https://www.linkedin.com/in/kingsley-ahams-b92142274/", gh: "https://github.com/Ahams-K", img: "/images/Kingsley.jpeg" },
    { name: "Wajhudin", role: "Interface Engineer", li: "https://www.linkedin.com/in/wajhudin-ibrahim-55b5a030a/", gh: "#", img: "/images/Wajhudin.jpg" }
];

export default function Team() {
    return (
        <section id="team" className="py-32 px-6 bg-[#050505]">
            <div className="max-w-6xl mx-auto">
                <h2 className="text-4xl font-bold text-white mb-16 tracking-tight">Engineering Unit</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                    {team.map((m, i) => (
                        <div key={i} className="group relative bg-[#0a0a0a] border border-white/5 rounded-3xl p-8 hover:border-blue-500/50 transition-all duration-500">
                            <div className="relative z-10 flex flex-col items-center text-center">
                                {/* Profile Image Placeholder */}
                                <div className="w-48 h-48 rounded-2xl overflow-hidden border border-white/10 mb-6 group-hover:scale-105 transition-transform">
                                    <img src={m.img} alt={m.name} className="w-full h-full object-cover grayscale group-hover:grayscale-0 transition-all" />
                                </div>
                                <h4 className="text-2xl font-bold text-white">{m.name}</h4>
                                <p className="text-blue-500 font-mono text-[10px] uppercase tracking-[0.3em] mb-8">{m.role}</p>

                                <div className="w-full space-y-3">
                                    <a href={m.li} className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5 hover:bg-blue-600/10 transition group/link">
                                        <div className="flex items-center gap-3">
                                            <Linkedin size={18} className="text-blue-400" />
                                            <span className="text-sm font-medium text-gray-300">LinkedIn</span>
                                        </div>
                                        <ExternalLink size={14} className="text-gray-600 group-hover/link:text-white" />
                                    </a>
                                    <a href={m.gh} className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5 hover:bg-white/10 transition group/link">
                                        <div className="flex items-center gap-3">
                                            <Github size={18} className="text-white" />
                                            <span className="text-sm font-medium text-gray-300">GitHub</span>
                                        </div>
                                        <ExternalLink size={14} className="text-gray-600 group-hover/link:text-white" />
                                    </a>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}