import JobStatus from '@/components/JobStatus';

export default function JobPage({ params }: { params: { id: string } }) {
  return (
    <div className="py-8">
      <JobStatus jobId={params.id} />
    </div>
  );
}
