import { lazy, Suspense } from 'react'
import '@fontsource-variable/geist/wght.css'
import '@fontsource-variable/geist-mono/wght.css'
import Chapters from '../components/landing/Chapters.jsx'
import Defer from '../components/landing/Defer.jsx'
import Link from '../components/landing/Link.jsx'
import Logo from '../components/landing/Logo.jsx'
import Nav from '../components/landing/Nav.jsx'
import Hero from '../components/landing/sections/Hero.jsx'
import { useVoiceStage } from '../components/landing/stage/useVoiceStage.js'
import '../styles/tokens.css'
import '../components/landing/landing.css'

const VoiceStage = lazy(() => import('../components/landing/stage/VoiceStage.jsx'))
const Explain = lazy(() => import('../components/landing/sections/Explain.jsx'))
const Demo = lazy(() => import('../components/landing/sections/Demo.jsx'))
const UseCases = lazy(() => import('../components/landing/sections/UseCases.jsx'))
const HowItWorks = lazy(() => import('../components/landing/sections/HowItWorks.jsx'))
const ConfigPreview = lazy(() => import('../components/landing/sections/ConfigPreview.jsx'))
const Architecture = lazy(() => import('../components/landing/sections/Architecture.jsx'))
const RealtimeMatters = lazy(() => import('../components/landing/sections/RealtimeMatters.jsx'))
const CallToAction = lazy(() => import('../components/landing/sections/CallToAction.jsx'))

// The public site. It renders at once (text, CSS orb, buttons); the 3D scene and every section
// below the hero are fetched afterwards, so the first paint never waits for them.
export default function Landing() {
    const voiceStage = useVoiceStage()

    return (
        <div className="lp" data-stage={voiceStage.status}>
            <Nav />
            <Chapters />

            {voiceStage.enabled && (
                <VoiceStageBoundary
                    tier={voiceStage.tier}
                    onReady={voiceStage.onReady}
                    onGiveUp={voiceStage.onGiveUp}
                />
            )}

            <main>
                <Hero />
                <Defer id="what" chapter="What it is" minHeight="430vh">
                    <Explain />
                </Defer>
                <Defer id="demo" chapter="Live demo" minHeight="820px">
                    <Demo />
                </Defer>
                <Defer id="use-cases" chapter="What it can do" minHeight="330vh">
                    <UseCases />
                </Defer>
                <Defer id="how" chapter="How it works" minHeight="640vh">
                    <HowItWorks />
                </Defer>
                <Defer id="build" chapter="Build an agent" minHeight="860px">
                    <ConfigPreview />
                </Defer>
                <Defer id="architecture" chapter="The real-time loop" minHeight="900px">
                    <Architecture />
                </Defer>
                <Defer id="realtime" chapter="Why real-time" minHeight="1000px">
                    <RealtimeMatters />
                </Defer>
                <Defer id="get-started" chapter="Get started" minHeight="100vh">
                    <CallToAction />
                </Defer>
            </main>

            <footer className="lp-footer">
                <div className="lp-wrap">
                    <Link to="/" className="lp-brand">
                        <Logo />
                        <span>
                            <b>Real-Time</b> Voice Agent
                        </span>
                    </Link>
                    <nav aria-label="Footer">
                        <Link to="/checkin" transition>
                            Sign in
                        </Link>
                        <Link to="/checkin?mode=register" transition>
                            Sign up
                        </Link>
                    </nav>
                </div>
            </footer>
        </div>
    )
}

function VoiceStageBoundary(props) {
    return (
        <Suspense fallback={null}>
            <VoiceStage {...props} />
        </Suspense>
    )
}
