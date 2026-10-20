import { render, screen } from '@testing-library/react'
import LineChart, { niceTicks, seriesColor } from './LineChart'
import { bucketLabels } from '../Dashboard/UsageGraph'

describe('niceTicks', () => {
    it('gives an integer scale even for empty data', () => {
        expect(niceTicks(0)).toEqual([0, 1, 2, 3, 4])
    })
    it('rounds the top up to a round number', () => {
        expect(niceTicks(23)).toEqual([0, 10, 20, 30])
        expect(niceTicks(7)).toEqual([0, 2, 4, 6, 8])
    })
    it('allows fractions for hours', () => {
        expect(niceTicks(0.3, { integer: false })).toEqual([0, 0.5, 1])
    })
})

describe('LineChart', () => {
    const labels = ['a', 'b', 'c']
    it('joins points with straight segments, one line per series, and lists them in the legend', () => {
        const { container } = render(
            <LineChart
                labels={labels}
                series={[
                    { id: '1', name: 'Ava', color: seriesColor(0), points: [0, 5, 0] },
                    { id: '2', name: 'Ben', color: seriesColor(1), points: [1, 1, 1] },
                ]}
            />,
        )
        expect(container.querySelectorAll('polyline')).toHaveLength(2)
        expect(container.querySelector('path')).toBeNull() // no curves
        const legend = screen.getByRole('list', { name: 'Legend' })
        expect(legend).toHaveTextContent('Ava')
        expect(legend).toHaveTextContent('Ben')
        expect(screen.queryByText(/No data/)).not.toBeInTheDocument()
    })
    it('shows an empty state for all-zero data and still draws the lines', () => {
        const { container } = render(
            <LineChart
                labels={labels}
                series={[{ id: '1', name: 'Ava', color: seriesColor(0), points: [0, 0, 0] }]}
            />,
        )
        expect(screen.getByText(/No data for this period/)).toBeInTheDocument()
        expect(container.querySelectorAll('polyline')).toHaveLength(1)
    })
    it('handles a single data point and no series', () => {
        const { container, rerender } = render(
            <LineChart labels={['a']} series={[{ id: '1', name: 'Ava', color: 'red', points: [3] }]} />,
        )
        expect(container.querySelector('circle')).not.toBeNull()
        rerender(<LineChart labels={labels} series={[]} />)
        expect(screen.getByRole('list', { name: 'Legend' }).children).toHaveLength(0)
    })
})

describe('bucketLabels', () => {
    it('shows hours for today and dates otherwise, from the zone-local part of the instant', () => {
        expect(bucketLabels(['2026-10-20T15:00:00+05:30'], 'today')).toEqual(['15:00'])
        expect(bucketLabels(['2026-10-20T00:00:00+00:00'], '7d')[0]).toMatch(/20/)
    })
})
