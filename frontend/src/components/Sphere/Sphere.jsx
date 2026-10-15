import { Canvas, useFrame } from '@react-three/fiber'
import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
export function sphereMode(status, agent) {
    if (status === 'connecting' || status === 'waiting_for_agent' || status === 'reconnecting')
        return 'connecting'
    if (status !== 'connected') return 'idle'
    if (agent === 'speaking') return 'speaking'
    if (agent === 'thinking') return 'thinking'
    return 'listening'
}
const COLORS = {
    idle: '#9aa0a6',
    connecting: '#c9a227',
    listening: '#3b82f6',
    thinking: '#8b5cf6',
    speaking: '#f97316',
}
function Blob({ mode, getLevels, reducedMotion }) {
    const mesh = useRef(null)
    const geo = useMemo(() => new THREE.IcosahedronGeometry(1, 14), [])
    const base = useMemo(() => Float32Array.from(geo.attributes.position.array), [geo])
    const color = useMemo(() => new THREE.Color(COLORS.idle), [])
    const target = useMemo(() => new THREE.Color(), [])
    useEffect(() => () => geo.dispose(), [geo])
    useFrame(({ clock }) => {
        const m = mesh.current
        if (!m) return
        const t = clock.getElapsedTime()
        const { user, agent } = getLevels()
        // user speech drives vibration while listening; agent speech drives it while speaking
        const level =
            mode === 'speaking' ? agent : mode === 'listening' ? user : mode === 'thinking' ? 0.12 : 0.04
        const amp = (reducedMotion ? 0.25 : 1) * (0.04 + level * 0.55)
        const g = m.geometry
        const pos = g.attributes.position
        for (let i = 0; i < pos.count; i++) {
            const x = base[i * 3],
                y = base[i * 3 + 1],
                z = base[i * 3 + 2]
            const n = Math.sin(x * 3 + t * 2.1) * Math.sin(y * 3.3 + t * 1.7) * Math.sin(z * 2.7 + t * 2.4)
            const k = 1 + amp * n
            pos.setXYZ(i, x * k, y * k, z * k)
        }
        pos.needsUpdate = true
        g.computeVertexNormals()
        if (!reducedMotion) m.rotation.y += 0.003
        color.lerp(target.set(COLORS[mode]), 0.08)
        m.material.color.copy(color)
    })
    return (
        <mesh ref={mesh} geometry={geo}>
            <meshStandardMaterial roughness={0.35} metalness={0.1} />
        </mesh>
    )
}
export default function Sphere(props) {
    const [visible, setVisible] = useState(() => document.visibilityState !== 'hidden')
    useEffect(() => {
        const h = () => setVisible(document.visibilityState !== 'hidden')
        document.addEventListener('visibilitychange', h)
        return () => document.removeEventListener('visibilitychange', h)
    }, [])
    return (
        <div className="sphere" role="img" aria-label={`Voice agent is ${props.mode}`}>
            <Canvas frameloop={visible ? 'always' : 'never'} camera={{ position: [0, 0, 3.2], fov: 45 }}>
                <ambientLight intensity={0.7} />
                <directionalLight position={[3, 3, 4]} intensity={1.2} />
                <Blob {...props} />
            </Canvas>
        </div>
    )
}
