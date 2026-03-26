export default function Video() {
    return (
        <section id="video" className="min-h-screen py-16 sm:py-24 px-4 sm:px-6">
            <h2 className="text-2xl sm:text-3xl font-bold mb-6 sm:mb-10 text-center">
                System Demo
            </h2>

            <div className="flex justify-center">
                <video
                    controls
                    className="w-full max-w-3xl rounded-xl border border-[#222]"
                >
                    <source src="/video/last_vid.mp4" type="video/mp4" />
                    Your browser does not support the video tag.
                </video>
            </div>
        </section>
    );
}