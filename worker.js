import { Container } from '@cloudflare/containers';

// Container-based Durable Object for PDF Splitter
export class PDFSplitter extends Container {
  defaultPort = 8000;
  sleepAfter = '30s'; // Keep container alive for 30 seconds after last request
  
  // Environment variables for the container
  envVars = {
    SERVICE_NAME: 'pdf-splitter',
    VERSION: '1.0.0'
  };

  onStart() {
    console.log('PDF Splitter container successfully started');
  }

  onStop() {
    console.log('PDF Splitter container successfully shut down');
  }

  onError(error) {
    console.error('PDF Splitter container error:', error);
  }
}

export default {
  async fetch(request, env) {
    // Get or create a container instance
    const container = env.PDF_SPLITTER.getByName('pdf-splitter-main');
    
    // Forward all requests to the container
    return await container.fetch(request);
  }
};