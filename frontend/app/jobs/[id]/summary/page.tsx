import SummaryViewer from '@/components/SummaryViewer';

export default function SummaryPage({ params }: { params: { id: string } }) {
  return (
    <div className="py-8">
      <SummaryViewer jobId={params.id} />
    </div>
  );
}
