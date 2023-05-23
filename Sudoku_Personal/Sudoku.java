public class Sudoku {
    public static void solucion(int[][]matriz, boolean[][]visitados) { //Resolución de sudokus, mediante backtracking
        Matriz.inicializarVisitados(matriz, visitados);
        solucionAux(matriz, visitados, 0, 0);
        Matriz.printValores(matriz);
    }

    public static boolean solucionAux(int[][]matriz, boolean[][]visitados, int fila, int columna) {
        int valor = 1;
        int N = matriz.length;
        int i = 0, j = 0;
        boolean solucion = visitados[0][0];
        while (solucion && (i < N-1 || j < N-1)) { //Comprobación de visitados en todos los cuadros
            if (j < N-1) j++;
            else{
                j = 0;
                i++;
            }
            if (!visitados[i][j]) solucion = false;
        }
        i = fila;
        j= columna;
        for (; i < N; i++) { //Se empiezan todos los caminos
            for (; j < N; j++) {
                while (!visitados[i][j] && valor < 10 && !solucion) { //Considerando todos los posibles candidatos para rellenar casilla
                    if (Sudoku.factible(matriz, valor, i, j)) {
                        visitados[i][j] = true;
                        matriz[i][j] = valor;
                        solucion = solucionAux(matriz, visitados, i, j);
                        if (!solucion) {
                            matriz[i][j] = 0;
                            visitados[i][j] = false;
                        }
                    }
                    valor++;
                }
            }
            j=0;
        }
        return solucion;
    }

    public static boolean factible(int[][] matriz, int valor, int fila, int columna) {
        boolean aceptable = true;
        int i = 0, j = 0;
        int N = matriz.length;
        while (aceptable && ((i < N-1) || (j < N-1))) { //Comprobación para evitar repeticiones en fila o columna
            if (matriz[fila][j] == valor || matriz[i][columna] == valor) aceptable = false;
            if (j < N - 1) j++; //Moviendo columnas para verificar
            else if (i < N - 1) i++; //Moviendo filas para verificar
        }

        //Reiniciando contadores
        i = 0;
        j = 0;

        //Manipulando valores para determinar cuadrante:
        fila /= 3;
        columna /= 3;
        fila *= 3;
        columna *= 3;
        while (aceptable && ((i < 2) || (j < 2))) { //Comprobación para evitar repeticiones en un mismo cuadrante
            if (matriz[fila + i][columna + j] == valor) aceptable = false;
            if (j < 2) j++;
            else{
                j = 0;
                i++;
            }
        }
        return aceptable;
    }
}
