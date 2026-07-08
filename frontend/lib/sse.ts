export async function* parseSSE<T = unknown>(response: Response): AsyncGenerator<T> {
  if (!response.body) {
    throw new Error("Missing response body for SSE stream");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      for (const line of chunk.split("\n")) {
        if (!line.startsWith("data: ")) {
          continue;
        }
        const payload = line.slice(6).trim();
        if (!payload) {
          continue;
        }
        yield JSON.parse(payload) as T;
      }
    }
  }
}

